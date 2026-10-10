/* SSH Web Bridge - MRE keypad client. The SSH credentials and commands stay on the gateway. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmhttp.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include <stdio.h>
#include <string.h>

#define RGB565(r,g,b) (VMUINT16)((((r)&0xF8)<<8)|(((g)&0xFC)<<3)|((b)>>3))
#define TEXT_MAX 180

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static VMINT g_tick = 0;
static VMINT g_busy = 0;
static VMINT g_pairing = 0;
static VMINT g_selected = 0;
static VMINT g_page = 0;
static VMINT g_confirm_key = 0;
static VMINT g_confirm_tick = 0;
static char g_base_url[190] = "";
static char g_target[33] = "homelab";
static char g_pair_code[13] = "";
static char g_session_token[96] = ""; /* RAM only; expires server-side after 30 minutes. */
static char g_status[52] = "Set up gateway with key 0";
static char g_result[256] = "No response yet";
static VMUINT8 g_response_buf[4096];

static http_request_t g_request;
static http_session_t g_session;
static http_head_t g_headers[2];
static asyn_http_req_t g_async_request;
static char g_request_body[180];
static char g_request_url[255];
static const char* const ACTION_IDS[4] = {"lights_on", "gate_open", "house_temp", "sleep_mode"};
static void consume_response(VMINT code, void* payload);
static void http_state(VMINT state, VMINT param, void* session);

static VMUINT16* framebuffer(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void rect(int x, int y, int w, int h, VMUINT16 color) {
    VMUINT16* fb = framebuffer();
    if (fb) vxpe2d_fill_rect((uint16_t*)fb, vm_graphic_get_screen_width(), vm_graphic_get_screen_height(), x, y, w, h, color);
}

static void frame(int x, int y, int w, int h, VMUINT16 color) {
    rect(x, y, w, 1, color); rect(x, y+h-1, w, 1, color);
    rect(x, y, 1, h, color); rect(x+w-1, y, 1, h, color);
}

static void text(int x, int y, const char* s, VMUINT16 color) {
    VMWCHAR wide[96];
    int i = 0;
    while (s[i] && i < 94) { wide[i] = (VMWCHAR)(unsigned char)s[i]; ++i; }
    wide[i] = 0;
    vm_graphic_textout((VMUINT8*)framebuffer(), x, y, wide, i, color);
}

static void draw(void) {
    int i;
    int offset=0;
    char line[40];
    VMUINT16* fb;
    if (g_layer < 0) return;
    fb = framebuffer();
    if (!fb) return;
    /* RetroMRE paper-utility layout: warm paper, burnt-orange chrome,
       peach selection and compact keypad-first rows. */
    vxpe2d_fill_rect((uint16_t*)fb, vm_graphic_get_screen_width(), vm_graphic_get_screen_height(),
        0, 0, vm_graphic_get_screen_width(), vm_graphic_get_screen_height(), RGB565(247,242,231));
    vm_graphic_set_font(VM_SMALL_FONT);
    rect(0, 16, 240, 24, RGB565(200,90,30));
    rect(0, 38, 240, 2, RGB565(156,74,24));
    text(8, 21, "VXP REMOTE", RGB565(255,243,232));
    text(183, 21, g_page == 0 ? "1/3" : (g_page == 1 ? "2/3" : "3/3"), RGB565(255,243,232));
    rect(0, 40, 240, 22, RGB565(239,232,216));
    rect(0, 61, 240, 1, RGB565(210,198,180));
    rect(g_page == 0 ? 0 : (g_page == 1 ? 80 : 171), 40,
         g_page == 0 ? 78 : (g_page == 1 ? 91 : 69), 21, RGB565(200,90,30));
    text(17, 46, "HOME", g_page == 0 ? RGB565(255,243,232) : RGB565(74,64,56));
    text(96, 46, "BLUETOOTH", g_page == 1 ? RGB565(255,243,232) : RGB565(74,64,56));
    text(194, 46, "ABOUT", g_page == 2 ? RGB565(255,243,232) : RGB565(74,64,56));
    rect(7, 65, 226, 13, RGB565(247,242,231));
    if (g_page == 0) text(10, 66, g_status, RGB565(74,64,56));

    if (g_page != 0) {
        rect(7, 80, 226, 213, RGB565(242,234,216));
        frame(7, 80, 226, 213, RGB565(201,187,168));
        rect(8, 81, 224, 19, RGB565(43,43,43));
        text(15, 86, g_page == 1 ? "BLUETOOTH MOUSE" : "ABOUT VXP REMOTE", RGB565(255,243,232));
        if (g_page == 2) {
            text(15, 118, "SSH WEB BRIDGE CLIENT", RGB565(42,36,28));
            text(15, 143, "RetroMRE-inspired keypad UI", RGB565(74,64,56));
            text(15, 164, "240 x 320  |  MRE / VXPEngine", RGB565(74,64,56));
            text(15, 190, "© VXPstore. All rights reserved.", RGB565(74,64,56));
            text(15, 219, "LEFT/RIGHT: SWITCH PAGE", RGB565(156,74,24));
        } else {
        text(15, 112, "MRE RADIO: CLASSIC BT / SPP", RGB565(42,36,28));
        text(15, 133, "HID DEVICE PROFILE: UNAVAILABLE", RGB565(156,74,24));
        text(15, 157, "This firmware SDK exposes SPP", RGB565(74,64,56));
        text(15, 171, "serial, not a standard mouse HID.", RGB565(74,64,56));
        text(15, 199, "A paired computer needs a small", RGB565(74,64,56));
        text(15, 213, "SPP-to-pointer helper. Phones need", RGB565(74,64,56));
        text(15, 227, "a companion app/accessibility setup.", RGB565(74,64,56));
        text(15, 255, "Direct plug-and-play mouse pairing", RGB565(74,64,56));
        text(15, 269, "cannot be enabled by this VXP alone.", RGB565(74,64,56));
        }
        rect(0, 300, 240, 20, RGB565(239,232,216));
        rect(0, 300, 240, 1, RGB565(210,198,180));
        text(6, 305, "LEFT/RIGHT: SWITCH PAGE", RGB565(74,64,56));
        text(177, 305, "BACK EXIT", RGB565(42,36,28));
        vm_graphic_flush_layer(&g_layer, 1);
        return;
    }

    for (i = 0; i < 4; ++i) {
        int y = 80 + i * 37;
        VMUINT16 base = (i == g_selected) ? RGB565(245,201,168) : RGB565(247,242,231);
        rect(7, y, 226, 32, base);
        rect(7, y+31, 226, 1, RGB565(210,198,180));
        if (i == g_selected) rect(7, y, 2, 32, RGB565(192,64,32));
        text(14, y+9, (const char* const[]){"1  LIGHTS TOGGLE", "2  OPEN GARAGE GATE", "3  HOUSE TEMPERATURE", "4  SLEEP MODE"}[i], RGB565(42,36,28));
    }

    rect(7, 234, 226, 59, RGB565(242,234,216));
    frame(7, 234, 226, 59, RGB565(201,187,168));
    rect(8, 235, 224, 15, RGB565(43,43,43));
    text(14, 238, "GATEWAY RESULT", RGB565(255,243,232));
    for (i=0; i<3 && g_result[offset]; ++i) {
        int n=0;
        while (g_result[offset] && n<34) line[n++]=g_result[offset++];
        line[n]=0;
        text(14, 254+i*11, line, RGB565(42,36,28));
    }
    rect(0, 300, 240, 20, RGB565(239,232,216));
    rect(0, 300, 240, 1, RGB565(210,198,180));
    text(6, 305, "1-4 ACTION   0 SETUP   * PAIR", RGB565(74,64,56));
    text(177, 305, "OK RUN", RGB565(42,36,28));
    vm_graphic_flush_layer(&g_layer, 1);
}

static void copy_input(char* dst, int dst_size, VMWSTR src) {
    int i;
    if (!dst || dst_size <= 0) return;
    dst[0] = 0;
    if (!src) return;
    for (i=0; i<dst_size-1 && src[i]; ++i) {
        if (src[i] < 0 || src[i] > 127) break;
        dst[i]=(char)src[i];
    }
    dst[i]=0;
}

static void begin_url_input(void);
static void begin_target_input(void);
static void begin_pair_code_input(void);

static void pair_complete(VMINT state, VMWSTR input) {
    size_t i;
    if (state != VM_INPUT_OK) { strcpy(g_status, "Pair code not entered"); draw(); return; }
    copy_input(g_pair_code, sizeof(g_pair_code), input);
    if (strlen(g_pair_code) < 8 || strlen(g_pair_code) > 12) { strcpy(g_status, "Pair code must be 8-12 digits"); draw(); return; }
    for (i=0; g_pair_code[i]; ++i) if (g_pair_code[i]<'0' || g_pair_code[i]>'9') {
        strcpy(g_status, "Pair code must use digits only"); draw(); return;
    }
    g_pairing = 1;
    g_busy = 1;
    strcpy(g_status, "Pairing securely...");
    snprintf(g_request_body, sizeof(g_request_body), "{\"code\":\"%s\"}", g_pair_code);
    strcpy(g_request_url, g_base_url); strcat(g_request_url, "/api/pair");
    memset(&g_request, 0, sizeof(g_request));
    memset(&g_session, 0, sizeof(g_session));
    memset(g_headers, 0, sizeof(g_headers));
    memset(&g_async_request, 0, sizeof(g_async_request));
    strcpy(g_headers[0].name, "Content-Type"); strcpy(g_headers[0].value, "application/json");
    g_request.heads = g_headers; g_request.nhead = 1;
    strcpy(g_request.url, g_request_url);
    g_request.body = g_request_body; g_request.nbody = (int)strlen(g_request_body);
    g_async_request.req_method = POST; g_async_request.use_proxy = HTTP_USE_CMNET_PRIORITY; g_async_request.http_request = &g_request;
    if (vm_asyn_http_req(&g_async_request, consume_response, http_state) != ASYN_HTTP_REQ_ACCEPT_SUCCESS) {
        g_busy = 0; g_pair_code[0]=0; g_request_body[0]=0; strcpy(g_status, "HTTP request could not start"); draw();
    }
}

static void target_complete(VMINT state, VMWSTR input) {
    int i;
    if (state != VM_INPUT_OK) { strcpy(g_status, "Setup cancelled"); draw(); return; }
    copy_input(g_target, sizeof(g_target), input);
    if (!g_target[0]) strcpy(g_target, "homelab");
    for (i=0; g_target[i]; ++i) {
        char c=g_target[i];
        if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-')) {
            strcpy(g_status, "Target ID: letters, digits, _ - only"); draw(); return;
        }
    }
    begin_pair_code_input();
}

static void url_complete(VMINT state, VMWSTR input) {
    size_t n;
    size_t i;
    if (state != VM_INPUT_OK) { strcpy(g_status, "Setup cancelled"); draw(); return; }
    copy_input(g_base_url, sizeof(g_base_url), input);
    n = strlen(g_base_url);
    while (n && g_base_url[n-1] == '/') g_base_url[--n] = 0;
    if (strncmp(g_base_url, "https://", 8) != 0 || n < 12 || n > 180) {
        strcpy(g_status, "Use HTTPS gateway URL (key 0)"); draw(); return;
    }
    for (i=0; i<n; ++i) {
        char c=g_base_url[i];
        if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c==':'||c=='/'||c=='.'||c=='-'||c=='_')) {
            strcpy(g_status, "URL has unsupported characters"); draw(); return;
        }
    }
    begin_target_input();
}

static void begin_pair_code_input(void) {
    static VMWCHAR empty[2] = {0,0};
    static VMWCHAR title[24] = {'P','a','i','r',' ','c','o','d','e',0};
    vm_input_set_editor_title(title);
    (void)vm_input_text3(empty, 12, VM_INPUT_METHOD_NUMERIC, pair_complete);
}

static void begin_target_input(void) {
    static VMWCHAR initial[40];
    static VMWCHAR title[24] = {'T','a','r','g','e','t',' ','I','D',0};
    int i;
    for (i=0; g_target[i] && i<38; ++i) initial[i]=(VMWCHAR)(unsigned char)g_target[i];
    initial[i]=0;
    vm_input_set_editor_title(title);
    (void)vm_input_text3(initial, 32, VM_INPUT_METHOD_ALPHABETIC_EXT, target_complete);
}

static void begin_url_input(void) {
    static VMWCHAR initial[192];
    static VMWCHAR title[32] = {'H','T','T','P','S',' ','G','a','t','e','w','a','y',' ','U','R','L',0};
    int i;
    for (i=0; g_base_url[i] && i<188; ++i) initial[i]=(VMWCHAR)(unsigned char)g_base_url[i];
    initial[i]=0;
    vm_input_set_editor_title(title);
    (void)vm_input_text3(initial, 190, VM_INPUT_METHOD_URL, url_complete);
}

static void consume_response(VMINT code, void* payload) {
    http_session_t* session = payload ? (http_session_t*)payload : &g_session;
    const char* body;
    char* output;
    int i, j;
    (void)code;
    g_busy = 0;
    if (!session || session->res_code < 200 || session->res_code >= 300 || !session->resbody || session->nresbody <= 0) {
        g_session_token[0] = 0;
        g_pairing = 0;
        g_pair_code[0] = 0;
        g_request_body[0] = 0;
        strcpy(g_status, "Pair/run failed; check URL or code");
        strcpy(g_result, "No response / HTTPS error");
        draw(); return;
    }
    if (session->nresbody >= (VMINT)sizeof(g_response_buf)) {
        g_pairing = 0; g_pair_code[0]=0; g_session_token[0]=0; g_request_body[0]=0;
        strcpy(g_status, "Gateway response is too large"); draw(); return;
    }
    memset(g_response_buf,0,sizeof(g_response_buf));
    memmove(g_response_buf,session->resbody,(size_t)session->nresbody);
    g_response_buf[session->nresbody]=0;
    body = (const char*)g_response_buf;
    if (g_pairing) {
        const char* key = strstr(body, "\"token\":\"");
        if (!key) { g_pairing=0; g_pair_code[0]=0; g_request_body[0]=0; strcpy(g_status, "Pair response missing token"); draw(); return; }
        key += 9;
        for (i=0; key[i] && key[i]!='"' && i<(int)sizeof(g_session_token)-1; ++i) g_session_token[i]=key[i];
        g_session_token[i]=0;
        g_pairing=0;
        g_pair_code[0]=0;
        strcpy(g_status, "Paired - session expires in 30 min");
        strcpy(g_result, "Session token held in RAM only");
    } else {
        const char* key = strstr(body, "\"output\":\"");
        if (!key) { strcpy(g_result, "Action completed"); }
        else {
            key += 10; output=g_result; j=0; i=0;
            while (key[i] && key[i]!='"' && j<(int)sizeof(g_result)-1) {
                if (key[i]=='\\' && key[i+1]) {
                    ++i;
                    output[j++]=(key[i]=='n'||key[i]=='r')?' ':key[i];
                } else output[j++]=key[i];
                ++i;
            }
            output[j]=0;
        }
        strcpy(g_status, "Gateway response received");
    }
    g_request_body[0]=0;
    draw();
}

static void http_state(VMINT state, VMINT param, void* session) {
    (void)state; (void)param; (void)session;
}

static void send_action(int index) {
    int length;
    if (g_busy) { strcpy(g_status, "Request already in progress"); draw(); return; }
    if (!g_session_token[0]) { strcpy(g_status, "Press 0 to set up gateway"); draw(); return; }
    if (index == 1 || index == 3) {
        if (g_confirm_key != index || g_tick - g_confirm_tick > 45) {
            g_confirm_key=index; g_confirm_tick=g_tick;
            strcpy(g_status, "Press same key again to confirm"); draw(); return;
        }
    }
    g_confirm_key=0;
    g_busy=1; g_pairing=0;
    strcpy(g_status, "Sending smart-home action...");
    snprintf(g_request_body,sizeof(g_request_body),"{\"target\":\"%s\",\"action\":\"%s\",\"confirm\":%s}",g_target,ACTION_IDS[index],(index==1||index==3)?"\"CONFIRM\"":"null");
    strcpy(g_request_url,g_base_url); strcat(g_request_url,"/api/run");
    memset(&g_request,0,sizeof(g_request)); memset(&g_session,0,sizeof(g_session)); memset(g_headers,0,sizeof(g_headers)); memset(&g_async_request,0,sizeof(g_async_request));
    strcpy(g_headers[0].name,"Authorization");
    snprintf(g_headers[0].value,sizeof(g_headers[0].value),"Bearer %s",g_session_token);
    strcpy(g_headers[1].name,"Content-Type"); strcpy(g_headers[1].value,"application/json");
    g_request.heads=g_headers; g_request.nhead=2; strcpy(g_request.url,g_request_url);
    g_request.body=g_request_body; length=(int)strlen(g_request_body); g_request.nbody=length;
    g_async_request.req_method=POST; g_async_request.use_proxy=HTTP_USE_CMNET_PRIORITY; g_async_request.http_request=&g_request;
    if (vm_asyn_http_req(&g_async_request,consume_response,http_state)!=ASYN_HTTP_REQ_ACCEPT_SUCCESS) {
        g_busy=0; strcpy(g_status,"HTTP request could not start");
    }
    draw();
}

static void pair_gateway(void) {
    begin_url_input();
}

static void tick(VMINT timer_id) {
    (void)timer_id;
    ++g_tick;
    if (g_confirm_key && g_tick - g_confirm_tick > 45) { g_confirm_key=0; strcpy(g_status,"Confirmation expired"); draw(); }
}

static void start(void) {
    if (g_layer < 0) g_layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);
    if (g_timer < 0) g_timer=vm_create_timer(1000,tick);
    draw();
}

static void stop(void) {
    if (g_timer>=0) { vm_delete_timer(g_timer); g_timer=-1; }
    if (g_busy) vm_cancel_all_http_sessions();
    g_busy=0; g_session_token[0]=0;
    g_pair_code[0]=0; g_request_body[0]=0;
    if (g_layer>=0) { vm_graphic_delete_layer(g_layer); g_layer=-1; }
}

void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    if (message==VM_MSG_CREATE || message==VM_MSG_ACTIVE) start();
    else if (message==VM_MSG_PAINT) draw();
    else if (message==VM_MSG_INACTIVE || message==VM_MSG_QUIT) { stop(); if (message==VM_MSG_QUIT) vm_exit_app(); }
}

void handle_keyevt(VMINT event, VMINT keycode) {
    int index=-1;
    if (event!=VM_KEY_EVENT_DOWN) return;
    if (keycode==VM_KEY_RIGHT_SOFTKEY || keycode==VM_KEY_CLEAR || keycode==VM_KEY_BACK) { vm_exit_app(); return; }
    if (keycode==VM_KEY_LEFT) { g_page = (g_page + 2) % 3; draw(); return; }
    if (keycode==VM_KEY_RIGHT) { g_page = (g_page + 1) % 3; draw(); return; }
    if (keycode==VM_KEY_UP) { g_selected=(g_selected+3)%4; draw(); return; }
    if (keycode==VM_KEY_DOWN) { g_selected=(g_selected+1)%4; draw(); return; }
    if (keycode==VM_KEY_NUM0) { pair_gateway(); return; }
    if (keycode==VM_KEY_NUM1) index=0;
    else if (keycode==VM_KEY_NUM2) index=1;
    else if (keycode==VM_KEY_NUM3) index=2;
    else if (keycode==VM_KEY_NUM4) index=3;
    else if (keycode==VM_KEY_OK) index=g_selected;
    else if (keycode==VM_KEY_STAR) { if (g_base_url[0]) begin_pair_code_input(); else pair_gateway(); return; }
    if (index>=0 && index<4) { g_selected=index; send_action(index); }
}

void handle_penevt(VMINT event, VMINT x, VMINT y) { (void)event; (void)x; (void)y; }

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
