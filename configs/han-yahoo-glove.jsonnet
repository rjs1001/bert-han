local _base = import 'han-yahoo.libsonnet';
local _data_path = 'data/yahoo_answers_csv';

function(args, data_path=_data_path) _base(output_from=true, data_path=data_path) + {
    local lr = 0.000743552663260837,
    local end_lr = 0,
    local bs = 20,

    local lr_s = '%0.1e' % lr,
    local end_lr_s = '0e0',
    model_name: 'bs=%(bs)d,lr=%(lr)s,end_lr=%(end_lr)s' % ({
        bs: bs,
        lr: lr_s,
        end_lr: end_lr_s,
    }),

    model+: {
        word_attention+: {
            dropout: 0.2,
            word_emb_size: 300,
        },   
        sentence_attention+: {
            dropout: 0.2,
            word_emb_size: 300,
        },
        preprocessor+: {
            word_emb: {
                name: 'glove',
                kind: '42B',
                lemmatize: true,
            },
            min_freq: 5,
            max_count: 30000,
        },
    },

    lr_scheduler+: {
        start_lr: lr,
        end_lr: end_lr,
    },
}
