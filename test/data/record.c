
struct S0 {
    int z;
};


/* #public(module2) */
struct S1 {
    int x;
    S0 y;
};

/* #private(module1) */
struct S2 {
    S1 s;
};

/* #private(module2) */
S1 *__wti_module2_func1(S2 *s2) {
    return &s2->s;
}
typedef struct S1 SSS1;
/* #public(module1) */
int func(int num) {
    S2 s2;
    s2;
    s2.s;
    s2.s.x;
    (&s2)->s;
    ((S1*)((S2*)s2)->s)->x;
    ((S1*)((S2*)s2 + 1)->s)->x;
    ((S1*)((S2*)s2 + 1)->s)->x;
    ((S1*)((S2*)s2[10])->s)->x;
    ((S2*)((S1*)((S2*)s2[10])->s)->x)->s;
    ((&(s2->s[i].y)))->z;
    xxx->s2;
    xxx()->s2;
    xxx.s2;
    __wti_module2_func1()->x;
    __wti_module2_func1()[5]->x;
    __wti_module2_func1(s2->s, s5)->x;
    s2->s.x;
    aa->bb->cc->dd;
    (aa->aaa)->bb->cc->dd;
    (5 ? s2 : s3)->s->x;
    (5 ? __wti_module2_func1() : s3)->x;
    ((S1){.x=5}).x;
    ((S1*)z)->y[s2->qwe1].z(s2->qwe2, s2->qwe3);
    ((S2*)s2 ? (S1*)NULL : (S0*)NULL)->x;
    ((S2*)s2 ? NULL : (S0*)NULL)->z;

    SSS1 s1, *ss1;
    S2 ss2;

    return num * num;
}

/* #private(module1) */
static S2 *__wti_module1_func2(void) {
    return 5;
}

/* #private(module2) */
static int __wti_module2_func2(void) {
    return __wti_module1_func2();
}

/* #private(module2) */
int __wti_module2_func3(void) {
    return __wti_module1_func2()->x;
}

static S2 *__wti_module1_funcX(void) {
    return 5;
}

int func_local_struct(int a, char b) {
    struct {
        S1 s1;
        S2 s2;
    } local_str;
    local_str.s1.x = a;
    local_str.s2.s.x = a;
}

/* #private(module1) */
struct ACCESS1 {
    int x;
    char y;
    struct ACCESS2 {
        int z;
    } z;
};

struct FNPTRS {
    int (*f1)(int);
    int (*f2)(int);
};

struct unnamed_members {
    union {
        struct {
            int member1;
            char member2;
        };
        char __padding[64];
    }
};

struct __wt_rwlock { /* Read/write lock */
    volatile union {
        uint64_t v; /* Full 64-bit value */
        struct {
            uint8_t current;         /* Current ticket */
            uint8_t next;            /* Next available ticket */
            uint8_t reader;          /* Read queue ticket */
            uint8_t readers_queued;  /* Count of queued readers */
            uint32_t readers_active; /* Count of active readers */
        } s;
    } u;

    int16_t stat_read_count_off;    /* read acquisitions offset */
    int16_t stat_write_count_off;   /* write acquisitions offset */
    int16_t stat_app_usecs_off;     /* waiting application threads offset */
    int16_t stat_int_usecs_off;     /* waiting server threads offset */
    int16_t stat_session_usecs_off; /* waiting session offset */

    WT_CONDVAR *cond_readers; /* Blocking readers */
    WT_CONDVAR *cond_writers; /* Blocking writers */
};
