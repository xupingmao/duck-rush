#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void print_help(const char* self_name) {
    printf("usage: %s source_text target_text\n", self_name);
}

void replace_stdin(const char* source, const char* target) {
    #define BUF_SIZE (1024*1024)
    char buf[BUF_SIZE];
    char output_buf[BUF_SIZE * 2];
    char* pout = NULL;
    FILE* fp = stdin;
    char* result = NULL;
    int prev = 0;
    int target_len = strlen(target);

    while ((result = fgets(buf, BUF_SIZE, fp)) != NULL) {
        printf("line: %s", buf);
        prev  = 0;
        index = strstr(buf + prev, source);
        if (index == NULL) {
            puts(target);
        } else {
            pout = output_buf;
            strncpy(pout, buf, index);
            pout += index;
            strcpy(pout, target);
            pout += target_len;
            
            while (index != NULL) {
                strncpy(output_buf + out_len, buf + index;)
                puts(target);
                prev  = index;
                index = strstr(buf + index, source);
            }
        }
    }
}

int main(int argc, char const *argv[]) {
    printf("argc=%d\n", argc);
    if (argc != 3) {
        print_help(argv[0]);
        exit(0);
    }

    replace_stdin(argv[1], argv[2]);
    return 0;
}
