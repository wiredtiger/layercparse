
renameFields({
    "__wt_connection_impl": {
        "ckpt_session":             "ckpt.session",
        "ckpt_tid":                 "ckpt.tid",
        "ckpt_tid_set":             "ckpt.tid_set",
        "ckpt_cond":                "ckpt.cond",
        "ckpt_most_recent":         "ckpt.most_recent",
        "ckpt_logsize":             "ckpt.logsize",
        "ckpt_signalled":           "ckpt.signalled",
        "ckpt_apply":               "ckpt.apply",
        "ckpt_apply_time":          "ckpt.apply_time",
        "ckpt_drop":                "ckpt.drop",
        "ckpt_drop_time":           "ckpt.drop_time",
        "ckpt_lock":                "ckpt.lock",
        "ckpt_lock_time":           "ckpt.lock_time",
        "ckpt_meta_check":          "ckpt.meta_check",
        "ckpt_meta_check_time":     "ckpt.meta_check_time",
        "ckpt_skip":                "ckpt.skip",
        "ckpt_skip_time":           "ckpt.skip_time",
        "ckpt_usecs":               "ckpt.usecs",
        "ckpt_scrub_max":           "ckpt.scrub_max",
        "ckpt_scrub_min":           "ckpt.scrub_min",
        "ckpt_scrub_recent":        "ckpt.scrub_recent",
        "ckpt_scrub_total":         "ckpt.scrub_total",
        "ckpt_prep_max":            "ckpt.prep_max",
        "ckpt_prep_min":            "ckpt.prep_min",
        "ckpt_prep_recent":         "ckpt.prep_recent",
        "ckpt_prep_total":          "ckpt.prep_total",
        "ckpt_time_max":            "ckpt.time_max",
        "ckpt_time_min":            "ckpt.time_min",
        "ckpt_time_recent":         "ckpt.time_recent",
        "ckpt_time_total":          "ckpt.time_total",
        "ckpt_prep_end":            "ckpt.prep_end",
        "ckpt_prep_start":          "ckpt.prep_start",
        "ckpt_timer_start":         "ckpt.timer_start",
        "ckpt_timer_scrub_end":     "ckpt.timer_scrub_end",
        "ckpt_progress_msg_count":  "ckpt.progress_msg_count",
        "ckpt_write_bytes":         "ckpt.write_bytes",
        "ckpt_write_pages":         "ckpt.write_pages",
        "last_ckpt_base_write_gen": "ckpt.last_base_write_gen",
    },
    # "__wt_session_impl": {
    # },
    # "__wt_btree": {
    #     "ckpt_bytes_allocated": "ckpt.bytes_allocated",
    #     "checkpoint_gen":       "ckpt.checkpoint_gen",
    # },
})
