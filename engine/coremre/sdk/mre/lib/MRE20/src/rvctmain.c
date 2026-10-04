#include <rt_misc.h>
#include <stdarg.h>
#include <rt_sys.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "vmsys.h"
#include "vmchset.h"
#include "vmlog.h"
#include "vmio.h"

#pragma import(__use_no_semihosting)
#pragma import(__use_no_semihosting_swi)
#pragma import(__use_iso8859_ctype)
#pragma import(__use_iso8859_collate)
#pragma import(__use_iso8859_monetary)
#pragma import(__use_iso8859_numeric)
#pragma import(__use_iso8859_locale)
#pragma import(__use_no_heap)
#pragma import(__user_libspace)

typedef VMINT (*vm_get_sym_entry_t)(char* symbol);
vm_get_sym_entry_t vm_get_sym_entry;
 
void *malloc(size_t size)
{
	return vm_malloc(size);
}

void free(void * ptr)
{
	vm_free(ptr);
}
 
__value_in_regs struct __argc_argv $Sub$$__ARM_get_argv(void *reserved)
{
    struct __argc_argv args = { /*argc*/0, /*argv*/NULL, /*r2*/0, /*r3*/0 };
    
    return args;
}      

void $Sub$$_sys_exit(int returncode)
{
    
}

int $Sub$$__aeabi_atexit(void (*func)(void *), void *arg, void *dso_handle)
{
    return 0;
}
int $Sub$$__cxa_atexit(void (*func)(void *), void *arg, void *dso_handle)
{
    return 0;
}

void $Sub$$_ttywrch(int ch)
{
    return;
}
struct thread_libspace_mini {
    int errno;
    unsigned int fpstatus;
};

static struct thread_libspace_mini init_libspace;

unsigned *__rt_fp_status_addr(void)
{
    return &init_libspace.fpstatus;
}

int printf(const char * __restrict format, ...)
{
    return 0;
}
int _printf(const char * __restrict format, ...)
{
    return 0;
}
int __0printf(const char * __restrict format, ...)
{
    return 0;
}
int __1printf(const char * __restrict format, ...)
{
    return 0;
}

int vprintf(const char * __restrict format, va_list arg)
{
    return 0;
}
int _vprintf(const char * __restrict format, va_list arg)
{
    return 0;
}
int __0vprintf(const char * __restrict format, va_list arg)
{
    return 0;
}
int __1vprintf(const char * __restrict format, va_list arg)
{
    return 0;
}
int puts(const char * s)
{
    return 0;
}

#undef putchar
int putchar(int c)
{
    return 0;
}

const char __stdin_name[] = ":tt:in";
const char __stdout_name[] = ":tt:out";
const char __stderr_name[] = ":tt:err";
FILEHANDLE _sys_open(const char *filename, int mode)
{
    if (strcmp(filename, __stdin_name) == 0) {
        return 0;
    }
    else if (strcmp(filename, __stdout_name) == 0) {
        return 1;
    }
    else if (strcmp(filename, __stderr_name) == 0) {
        return 2;
    }
    return -1;
}
int _sys_close(FILEHANDLE fh)
{
    return 0;
}
int _sys_read(FILEHANDLE fh, unsigned char * buf,
                 unsigned len, int mode)
{
    memset(buf, 0, len);
    return 0;
}
int _sys_write(FILEHANDLE fh, const unsigned char * buf,
                 unsigned len, int mode)
{
    return 0;
}
long _sys_flen(FILEHANDLE fh)
{
    return -1;
}
int _sys_seek(FILEHANDLE fh, long pos)
{
    return -1;
}
int _sys_istty(FILEHANDLE fh)
{
    return 1;
}
int _sys_ensure(FILEHANDLE fh)
{
    return 0;
}
int __backspace(FILE *stream)
{
    return EOF;
}

struct __FILE
{
    long __unused;
};
FILE __stdin, __stdout, __stderr;
FILE *__aeabi_stdin = &__stdin, *__aeabi_stdout = &__stdout, *__aeabi_stderr = &__stderr;

#undef  NOTSUPPORT_FUNCTION
#define NOTSUPPORT_FUNCTION

FILE *fopen(const char * __restrict filename,
            const char * __restrict mode) NOTSUPPORT_FUNCTION
{
    return NULL;
}

FILE *freopen(const char * __restrict filename,
              const char * __restrict mode,
              FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return NULL;
}

int fclose(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fprintf(FILE * __restrict stream,
            const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}

size_t fread(void * __restrict ptr,
             size_t size, size_t nmemb, FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

size_t fwrite(const void * __restrict ptr,
              size_t size, size_t nmemb, FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fputc(int c, FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fputs(const char * __restrict s, FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

void perror(const char * s)
{
}

 
/************ Part III: Disabled functions for all projects *******************/

int _fprintf(FILE * __restrict stream,
             const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __0fprintf(FILE * __restrict stream,
             const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __1fprintf(FILE * __restrict stream,
             const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
            
int fflush(FILE * stream) NOTSUPPORT_FUNCTION
{
    return 0;
}

void setbuf(FILE * __restrict stream,
            char * __restrict buf) NOTSUPPORT_FUNCTION
{

}

int setvbuf(FILE * __restrict stream,
            char * __restrict buf,
            int mode, size_t size) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fscanf(FILE * __restrict stream,
           const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int _fscanf(FILE * __restrict stream,
            const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __0fscanf(FILE * __restrict stream,
            const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int scanf(const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int _scanf(const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __0scanf(const char * __restrict format, ...) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int vfscanf(FILE * __restrict stream, const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int _vfscanf(FILE * __restrict stream, const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __0vfscanf(FILE * __restrict stream, const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int vscanf(const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int _vscanf(const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int __0vscanf(const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int vfprintf(FILE * __restrict stream,
             const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
int _vfprintf(FILE * __restrict stream,
              const char * __restrict format, va_list arg) NOTSUPPORT_FUNCTION
{
    return EOF;
}
            
int fgetc(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

char *fgets(char * __restrict s, int n,
            FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return NULL;
}

int getc(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

#undef getchar
int getchar(void) NOTSUPPORT_FUNCTION
{
    return EOF;
}

char *gets(char * s) NOTSUPPORT_FUNCTION
{
    return NULL;
}

int putc(int c, FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int ungetc(int c, FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

size_t __fread_bytes_avail(void * __restrict ptr,
                           size_t count, FILE * __restrict stream) NOTSUPPORT_FUNCTION
{
    return 0;
}

int fgetpos(FILE * __restrict stream, fpos_t * __restrict pos) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fseek(FILE * stream, long int offset, int whence) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int fsetpos(FILE * __restrict stream, const fpos_t * __restrict pos) NOTSUPPORT_FUNCTION
{
    return EOF;
}

long int ftell(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

void rewind(FILE * stream) NOTSUPPORT_FUNCTION
{

}

void clearerr(FILE * stream) NOTSUPPORT_FUNCTION
{

}

int feof(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int ferror(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

int _fisatty(FILE * stream) NOTSUPPORT_FUNCTION
{
    return EOF;
}

void rvct_entry(unsigned int entry) 
{
	vm_get_sym_entry = (vm_get_sym_entry_t)entry;
	__rt_lib_init(0,0);
	vm_main();
}
