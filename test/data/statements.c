
int __attribute__((xxx)) func(int a, int b) {
  int x;
  x = a + b;
  return (x);
}

func(5,6);

return func(5,6);

int x;

/* pre */
int *x; /* post */

a;

a, b;

*a;

*a, *b;

a = b;

*a = *b;

x = 5 + 8;

int x = 5 + 8;

__vector unsigned long long __v = {__a, __b};

/* comment */
/*
 * block comment
 */

// Preprocessor

/* pre comment */
#define qwe QWE /* post comment */

#define asd(x, y) ASD \
  ZXC /* post comment */

// typedef

/* pre comment */
typedef aa bbb; /* post comment */

/* pre comment */
typedef TAILQ_HEAD(aa,bb) tqh; /* post comment */

// records

/* pre comment */
struct {
  /* pre comment 2 */
  int a1, b1; /* post comment 2 */
  char c1;
}; /* post comment */

/* pre comment */
struct aaa {
  /* pre comment 2 */
  int a2, b2; /* post comment 2 */
  char c2;
}; /* post comment */

/* pre comment */
struct {
  /* pre comment 2 */
  int a3, b3; /* post comment 2 */
  char c3;
} bbb; /* post comment */

/* pre comment */
struct aaa {
  /* pre comment 2 */
  int a4, b4; /* post comment 2 */
  char c4;
} bbb, ccc; /* post comment */

/* pre comment */
typedef struct aaa {
  /* pre comment 2 */
  int a5, b5; /* post comment 2 */
  char c5;
} bbb, ccc; /* post comment */

/* pre comment */
union aaa {
  /* pre comment 2 */
  int a6, b6; /* post comment 2 */
  char c6;
} bbb, ccc; /* post comment */

/* pre comment */
typedef enum aaa {
  AAA1, BBB1, CCC1
} bbb, ccc; /* post comment */

/* pre comment */
typedef enum aaa {
  AAA2, BBB2, CCC2
} bbb, ccc; /* post comment */

/* pre comment */
typedef union aaa {
  /* pre comment 2 */
  int a7, b7; /* post comment 2 */
  struct aaabbb {
    int bbb7;
    struct aaabbbccc {
      int ccc7;
    } yyy7;
  } xxx7;
  char c7;
} bbb7, ccc7; /* post comment */

/* pre comment */
typedef union aaa8 {
  /* pre comment 2 */
  int a8, b8; /* post comment 2 */
  struct {
    int bbb8;
    struct {
      int ccc8;
    } yyy8;
  } xxx8;
  char c8;
} bbb8, ccc8; /* post comment */

int func(int a, int b);
void func(int a, int b) __attribute__((__noreturn__));
inline void func(int a, int b) __attribute__((__noreturn__));
WT_INLINE void func(int a, int b) __attribute__((__noreturn__));
void func_of_ptr(int *a[100]) {
}

/*
 * func --
 *      function description
 */
int func(int a, int b) {
  int x;
  x = a + b;
  return (x);
}

/*
 * func --
 *      function description
 */
static const int func2(int a, int b) {
}

do {
} while (0);


extern "C" {
  int func_ext_c(int a, int b);
  struct ext_c_struct; typedef struct ext_c_struct EXT_C_STRUCT;
  struct {
    int a9, b9;
  } ext_c_struct2;
}

#define AAA
#define BBB 5
#define CCC 5 + 8
#define DDD() 5 + 8
#define EEE(x) x + 8
#define FFF(x, y) x + y
#define GGG(x, y) x + \
 y

qwe asd;
qwe *asd;
qwe* asd;
qwe * asd;
qwe *;

int asd;
int *asd;
int* asd;
int * asd;
int *;

qwe = asd * zxc;
int qwe = asd * zxc;
qwe asd = {123, 456};
struct aaa {
  int a10, b10;
} bbb10 = {123, 456};
struct aaa bbb = {123, 456};

qwe *func1(int a, int b) {1}
qwe* func2(int a, int b) {2}
qwe * func3(int a, int b) {3}
qwe*func4(int a, int b) {4}

struct StructWithNested {
    struct {
        int x11;
        char y11;
    };
};

static const struct {
      int x;
} qwe = {123};

qwe * asd(int aa, int bb);
qwe * asd(int aa, int bb) {
}

qwe * (* asd)(int aa, int bb);
qwe * (* asd(void))(int aa, int bb) {
}

int (* asd)(int aa, int bb);
