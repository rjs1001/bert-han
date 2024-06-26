{
    logdir: "logdir/wanted_bert_run",
    model_config: "configs/wanted-bert.jsonnet",
    model_config_args: {
        bs: 32,
        bert_version: "bert-base-uncased", #"skt/kobert-base-v1",
        max_steps: 120000,
        lr: 7.44e-4,
        bert_lr: 3e-6,
        end_lr: 0,
    },

    test_name: "bert_run",
    test_output: "__LOGDIR__/ie_dirs",
    test_section: "test",
}