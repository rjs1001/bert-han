import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence, PackedSequence
from transformers import BertModel

from src.utils import registry


@registry.register("word_attention", "BERTWordAttention")
class WordAttention(torch.nn.Module):
    def __init__(
            self,
            device: str,
            recurrent_size: int,
            attention_dim: int,
            bert_version: str = "bert-base-uncased",
    ):
        super().__init__()
        self.attention_dim = attention_dim
        self.recurrent_size = recurrent_size
        self._device = device
        self.bert_model = BertModel.from_pretrained(bert_version, return_dict=False)

        # Maps BERT output to `attention_dim` sized tensor
        self.word_weight = nn.Linear(self.recurrent_size, self.attention_dim)

        # Word context vector (u_w) to take dot-product with
        self.context_weight = nn.Linear(self.attention_dim, 1)

    def recurrent_size(self):
        return self.recurrent_size

    def forward(self, docs, doc_lengths, sent_lengths, attention_masks, token_type_ids):
        """
        :param docs: encoded document-level data; LongTensor (num_docs, padded_doc_length, padded_sent_length)
        :param doc_lengths: unpadded document lengths; LongTensor (num_docs)
        :param sent_lengths: unpadded sentence lengths; LongTensor (num_docs, max_sent_len)
        :param attention_masks: BERT attention masks; LongTensor (num_docs, padded_doc_length, padded_sent_length)
        :param token_type_ids: BERT token type IDs; LongTensor (num_docs, padded_doc_length, padded_sent_length)
        :return: sentences embeddings, docs permutation indices, docs batch sizes, word attention weights
        """

        # Sort documents by decreasing order in length
        doc_lengths, doc_perm_idx = doc_lengths.sort(dim=0, descending=True)
        docs = docs[doc_perm_idx]
        sent_lengths = sent_lengths[doc_perm_idx]

        # Make a long batch of sentences by removing pad-sentences
        # i.e. `docs` was of size (num_docs, padded_doc_length, padded_sent_length)
        # -> `packed_sents.data` is now of size (num_sents, padded_sent_length)
        packed_sents = pack_padded_sequence(docs, lengths=doc_lengths.tolist(), batch_first=True)

        # effective batch size at each timestep
        docs_valid_bsz = packed_sents.batch_sizes

        # Make a long batch of sentence lengths by removing pad-sentences
        # i.e. `sent_lengths` was of size (num_docs, padded_doc_length)
        # -> `packed_sent_lengths.data` is now of size (num_sents)
        packed_sent_lengths = pack_padded_sequence(sent_lengths, lengths=doc_lengths.tolist(), batch_first=True)

        # Make a long batch of attention masks by removing pad-sentences
        # i.e. `docs` was of size (num_docs, padded_doc_length, padded_sent_length)
        # -> `packed_attention_masks.data` is now of size (num_sents, padded_sent_length)
        packed_attention_masks = pack_padded_sequence(attention_masks, lengths=doc_lengths.tolist(), batch_first=True)

        # Make a long batch of token_type_ids by removing pad-sentences
        # i.e. `docs` was of size (num_docs, padded_doc_length, padded_sent_length)
        # -> `token_type_ids.data` is now of size (num_sents, padded_sent_length)
        packed_token_type_ids = pack_padded_sequence(token_type_ids, lengths=doc_lengths.tolist(), batch_first=True)

        sents, sent_lengths, attn_masks, token_types = (
            packed_sents.data, packed_sent_lengths.data, packed_attention_masks.data, packed_token_type_ids.data
        )

        # Sort sents by decreasing order in sentence lengths
        sent_lengths, sent_perm_idx = sent_lengths.sort(dim=0, descending=True)
        sents = sents[sent_perm_idx]

        embeddings, pooled_out = self.bert_model(sents, attention_mask=attn_masks, token_type_ids=token_types)

        packed_words = pack_padded_sequence(embeddings, lengths=sent_lengths.tolist(), batch_first=True)

        # effective batch size at each timestep
        sentences_valid_bsz = packed_words.batch_sizes

        u_i = torch.tanh(self.word_weight(packed_words.data))
        u_w = self.context_weight(u_i).squeeze(1)
        val = u_w.max()
        att = torch.exp(u_w - val)

        # Restore as sentences by repadding
        att, _ = pad_packed_sequence(PackedSequence(att, sentences_valid_bsz), batch_first=True)

        att_weights = att / torch.sum(att, dim=1, keepdim=True)

        # Restore as sentences by repadding
        sents, _ = pad_packed_sequence(packed_words, batch_first=True)

        sents = sents * att_weights.unsqueeze(2)
        sents = sents.sum(dim=1)

        # Restore the original order of sentences (undo the first sorting)
        _, sent_unperm_idx = sent_perm_idx.sort(dim=0, descending=False)
        sents = sents[sent_unperm_idx]

        att_weights = att_weights[sent_unperm_idx]

        return sents, doc_perm_idx, docs_valid_bsz, att_weights
