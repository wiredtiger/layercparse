/*
 * Block comment
 */

/* pre-comment1 */
#define qwe /* post-comment1 */

/* pre-comment2 */
int x; /* post-comment2 */

/* pre-comment3 */
int func1(int x); /* post-comment3 */

/* pre-comment3 */
int func2(int x) {
  /* pre comment4 */
  int a, b; /* post comment4 */
  char c;
}

struct aaa;
typedef struct bbb ccc;

struct aaa {
  int a;
};

struct {
  int a;
} aaa;

struct {
  int a;
} aaa, *bbb;

typedef struct {
  int a;
} aaa, *bbb;

typedef struct xxx {
  /* pre comment5 */
  int a; /* post comment5 */
} aaa;

