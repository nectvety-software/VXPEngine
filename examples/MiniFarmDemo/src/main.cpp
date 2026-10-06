#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "vmres.h"
#include "vmmm.h"

#include "vxpgdx/VxpGdx.h"
#include "graphics/particles/VxpParticlePool.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

using namespace vxpe::gdx;
using namespace vxpe::gdx::scene2d;
using namespace vxpe::gdx::scene2d::ui;

#define SCREEN_W 240
#define SCREEN_H 320
#define WORLD_TILES 60
#define TILE_SIZE 16
#define WORLD_PX (WORLD_TILES*TILE_SIZE)
#define RGB565(r,g,b) vxpe2d_rgb565((r),(g),(b))

enum Direction { DIR_DOWN=0, DIR_LEFT=1, DIR_RIGHT=2, DIR_UP=3 };
enum Tool { TOOL_HOE=0, TOOL_SEED=1, TOOL_HARVEST=2, TOOL_WATER=3 };

static VMINT g_layer=-1,g_timer=-1;
static VMUINT16 g_frame[SCREEN_W*SCREEN_H];
static uint16_t g_cells[WORLD_TILES*WORLD_TILES];

static AssetManager<2> g_assets;
static Texture* g_texture=nullptr;
static TextureAtlas<96> g_atlas;
static TiledMap<2,2,2,16,4> g_map;
static TiledMapRenderer<96> g_map_renderer;
static OrthographicCamera g_camera(SCREEN_W,SCREEN_H);
static SpriteBatch g_batch;
static Animation g_walk[4];
static VxpeRectI g_walk_frames[4][5];
static VxpeParticlePool g_particles;

static VMUINT8* g_atlas_meta=nullptr;
static VMUINT8* g_map_res=nullptr;
static VMINT g_atlas_meta_size=0,g_map_size=0;

static Stage g_stage(SCREEN_W,SCREEN_H);
static Panel g_top_bar,g_bottom_bar,g_inventory;
static Label g_title,g_money_label,g_energy_label,g_tool_label,g_hint,g_inventory_title,g_status;
static List<16> g_inventory_list;
static ScrollPane g_inventory_scroll;

static int g_started=0,g_ui_ready=0,g_inventory_open=0;
static int g_player_x=8*16,g_player_y=18*16;
static Direction g_dir=DIR_DOWN;
static Tool g_tool=TOOL_HOE;
static int g_walk_ticks=0;
static int g_money=120,g_energy=100,g_day_ms=0;
static int g_anim_ms=0;
static int g_animal_x[3]={22*16,25*16,23*16};
static int g_animal_y[3]={17*16,17*16,19*16};
static VMUINT32 g_rng=0x13572468u;

static char g_money_text[32],g_energy_text[32],g_tool_text[32],g_status_text[48];

static VMUINT32 rnd32(){g_rng=g_rng*1664525u+1013904223u;return g_rng;}
static int clampi(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
static VMUINT16* layer_buffer(){return g_layer>=0?(VMUINT16*)vm_graphic_get_layer_buffer(g_layer):nullptr;}

static void* asset_load(const char* name,uint32_t* out_size){
    VMINT n=0;VMUINT8* p=vm_load_resource((char*)name,&n);
    if(out_size)*out_size=n>0?(uint32_t)n:0;
    return p;
}
static void asset_free(void* p){if(p)vm_free(p);}

static void set_status(const char* s){
    if(!s)s="";
    strncpy(g_status_text,s,sizeof(g_status_text)-1);
    g_status_text[sizeof(g_status_text)-1]='\0';
    g_status.setText(g_status_text);
}

static const char* tool_name(){
    static const char* n[]={"HOE","SEED","HARVEST","WATER"};
    return n[(int)g_tool];
}

static void update_hud(){
    snprintf(g_money_text,sizeof(g_money_text),"$ %d",g_money);
    snprintf(g_energy_text,sizeof(g_energy_text),"EN %d",g_energy);
    snprintf(g_tool_text,sizeof(g_tool_text),"TOOL: %s",tool_name());
    g_money_label.setText(g_money_text);
    g_energy_label.setText(g_energy_text);
    g_tool_label.setText(g_tool_text);
}

static void inventory_selected(List<16>&,int index,const char* item,void*){
    char b[48];snprintf(b,sizeof(b),"SELECT %d: %s",index+1,item?item:"");
    set_status(b);
}

static void setup_ui(){
    if(g_ui_ready)return;
    LabelStyle small{};small.textColor=RGB565(245,239,206);small.scale=1;
    LabelStyle gold=small;gold.textColor=RGB565(255,218,77);

    g_top_bar.setBounds(0,0,SCREEN_W,24);
    g_top_bar.setBackground(RGB565(35,63,35));
    g_top_bar.setBorder(RGB565(94,126,63),1);
    g_title.setText("MINI FARM / VXPGDX");g_title.setStyle(gold);g_title.setBounds(5,5,118,10);
    g_money_label.setStyle(gold);g_money_label.setBounds(150,5,42,10);
    g_energy_label.setStyle(small);g_energy_label.setBounds(194,5,44,10);
    g_top_bar.addActor(g_title);g_top_bar.addActor(g_money_label);g_top_bar.addActor(g_energy_label);

    g_bottom_bar.setBounds(0,280,SCREEN_W,40);
    g_bottom_bar.setBackground(RGB565(28,45,27));
    g_bottom_bar.setBorder(RGB565(106,85,48),1);
    g_tool_label.setStyle(gold);g_tool_label.setBounds(5,286-280,100,10);
    g_hint.setText("5 ACTION  0 TOOL  1 BAG");g_hint.setStyle(small);g_hint.setBounds(5,301-280,170,10);
    g_status.setText("");g_status.setStyle(small);g_status.setBounds(130,286-280,105,10);
    g_bottom_bar.addActor(g_tool_label);g_bottom_bar.addActor(g_hint);g_bottom_bar.addActor(g_status);

    g_inventory.setBounds(18,42,204,218);
    g_inventory.setBackground(RGB565(39,61,35));
    g_inventory.setBorder(RGB565(221,177,83),2);
    g_inventory_title.setText("INVENTORY");g_inventory_title.setStyle(gold);g_inventory_title.setBounds(8,7,120,12);
    g_inventory.addActor(g_inventory_title);

    static const char* items[]={
        "TURNIP SEED x5","POTATO SEED x3","CARROT SEED x2",
        "HOE","WATERING CAN","WOOD x12","STONE x8",
        "EGG x2","MILK x1","FLOWER x4","CORN SEED x6",
        "BERRY x3","WOOL x2","CHEESE x1"
    };
    ListStyle ls{};ls.rowHeight=18;ls.paddingX=4;ls.textScale=1;
    ls.backgroundColor=RGB565(28,43,25);ls.selectedColor=RGB565(83,116,52);
    ls.textColor=RGB565(236,234,204);ls.selectedTextColor=RGB565(255,231,122);
    g_inventory_list.setStyle(ls);
    g_inventory_list.setCallback(inventory_selected,nullptr);
    for(const char* s:items)g_inventory_list.addItem(s);

    ScrollPaneStyle ss{};ss.backgroundColor=RGB565(23,36,22);ss.backgroundAlpha=255;
    ss.scrollbarColor=RGB565(221,177,83);ss.scrollbarTrackColor=RGB565(52,67,41);ss.scrollbarWidth=3;
    g_inventory_scroll.setStyle(ss);g_inventory_scroll.setBounds(8,27,188,180);
    g_inventory_scroll.setWidget(g_inventory_list);
    g_inventory.addActor(g_inventory_scroll);
    g_inventory.setVisible(false);

    g_stage.addActor(g_top_bar);g_stage.addActor(g_bottom_bar);g_stage.addActor(g_inventory);
    update_hud();set_status("FARM READY");
    g_ui_ready=1;
}

static int load_game_assets(){
    g_assets.configure(asset_load,asset_free);
    if(!g_assets.loadTexture("farm_atlas.vxa8"))return 0;
    g_texture=g_assets.getTexture("farm_atlas.vxa8");
    if(!g_texture)return 0;

    g_atlas_meta=vm_load_resource((char*)"farm_atlas.vxat",&g_atlas_meta_size);
    g_map_res=vm_load_resource((char*)"farm.vxtm",&g_map_size);
    if(!g_atlas_meta||!g_map_res)return 0;
    if(!g_atlas.loadVxat(*g_texture,g_atlas_meta,(uint32_t)g_atlas_meta_size))return 0;
    if(!g_map.loadVxtm(g_map_res,(uint32_t)g_map_size))return 0;

    TiledMapTileLayer* ground=g_map.getLayer(0);
    if(!ground||!ground->cells)return 0;
    for(int i=0;i<WORLD_TILES*WORLD_TILES;++i)g_cells[i]=ground->cells[i];
    ground->cells=g_cells;

    const TiledMapObjectLayer* objects=g_map.findObjectLayer("Objects");
    if(objects){
        const TiledMapObject* spawn=objects->findObject("spawn");
        if(spawn){g_player_x=spawn->x+8;g_player_y=spawn->y+14;}
        const char* names[3]={"chicken","cow","sheep"};
        for(int i=0;i<3;++i){
            const TiledMapObject* o=objects->findObject(names[i]);
            if(o){g_animal_x[i]=o->x+8;g_animal_y[i]=o->y+12;}
        }
    }

    for(int dir=0;dir<4;++dir){
        for(int f=0;f<5;++f){
            char name[20];snprintf(name,sizeof(name),"farmer_%02d",dir*5+f+1);
            const AtlasRegion* ar=g_atlas.findRegion(name);
            if(!ar)return 0;
            g_walk_frames[dir][f]=ar->region.rect();
        }
        g_walk[dir]=Animation(*g_texture,g_walk_frames[dir],5,120,true,false);
    }
    g_map_renderer.setView(g_camera);
    g_map_renderer.setMaxTilesPerFrame(360);
    vxpe_particles_init(&g_particles,VXPE_PARTICLE_POOL_MAX);
    return 1;
}

static void free_game_assets(){
    if(g_atlas_meta){vm_free(g_atlas_meta);g_atlas_meta=nullptr;}
    if(g_map_res){vm_free(g_map_res);g_map_res=nullptr;}
    g_assets.clear();g_texture=nullptr;
}

static int solid_at_world(int x,int y){
    int tx=x/TILE_SIZE,ty=y/TILE_SIZE;
    if(tx<0||ty<0||tx>=WORLD_TILES||ty>=WORLD_TILES)return 1;
    return g_map.cellHasFlags(0,tx,ty,TileFlagSolid)?1:0;
}

static void update_camera(){
    int cx=clampi(g_player_x-SCREEN_W/2,0,WORLD_PX-SCREEN_W);
    int cy=clampi(g_player_y-SCREEN_H/2,0,WORLD_PX-SCREEN_H);
    g_camera.setPositionQ8(cx<<8,cy<<8);
}

static void move_player(int dx,int dy){
    if(g_inventory_open)return;
    int nx=clampi(g_player_x+dx,8,WORLD_PX-8);
    int ny=clampi(g_player_y+dy,12,WORLD_PX-4);
    if(!solid_at_world(nx,g_player_y+3))g_player_x=nx;
    if(!solid_at_world(g_player_x,ny+3))g_player_y=ny;
    if(dx<0)g_dir=DIR_LEFT;else if(dx>0)g_dir=DIR_RIGHT;
    else if(dy<0)g_dir=DIR_UP;else if(dy>0)g_dir=DIR_DOWN;
    g_walk_ticks=4;
    update_camera();
}

static void spawn_action_fx(int wx,int wy,uint16_t color){
    for(int i=0;i<10;++i){
        VxpeParticleSpawn p;memset(&p,0,sizeof(p));
        p.x=(int16_t)(wx+(int)(rnd32()%9)-4);p.y=(int16_t)(wy+(int)(rnd32()%7)-3);
        p.vx_q8=((int)(rnd32()%41)-20)*256;p.vy_q8=-((int)(rnd32()%35)+8)*256;
        p.ay_q8=35*256;p.lifetime_ms=(uint16_t)(280+rnd32()%260);
        p.color565=0xFFFFu;p.tint565=color;p.alpha_start=210;p.alpha_end=0;
        p.size_start=2;p.size_end=1;p.blend=VXPE_BLEND_ALPHA;
        vxpe_particles_spawn(&g_particles,&p);
    }
}

static void target_tile(int* tx,int* ty){
    static const int fx[4]={0,-1,1,0};
    static const int fy[4]={1,0,0,-1};
    *tx=clampi(g_player_x/TILE_SIZE+fx[(int)g_dir],0,WORLD_TILES-1);
    *ty=clampi(g_player_y/TILE_SIZE+fy[(int)g_dir],0,WORLD_TILES-1);
}

static void interact(){
    if(g_inventory_open)return;
    int tx,ty;target_tile(&tx,&ty);
    uint16_t raw=g_cells[ty*WORLD_TILES+tx];
    TiledMapCell c;c.raw=raw;
    int gid=g_map.cellTileId(c);
    int changed=0;
    if(g_tool==TOOL_HOE){
        if(gid==1&&g_energy>=2){g_cells[ty*WORLD_TILES+tx]=2;g_energy-=2;set_status("SOIL TILLED");changed=1;}
        else set_status("HOE NEEDS GRASS");
    }else if(g_tool==TOOL_SEED){
        if(gid==2&&g_energy>=1){g_cells[ty*WORLD_TILES+tx]=12;g_energy-=1;set_status("SEED PLANTED");changed=1;}
        else set_status("SEED NEEDS SOIL");
    }else if(g_tool==TOOL_HARVEST){
        if(gid==12&&g_energy>=1){g_cells[ty*WORLD_TILES+tx]=2;g_energy-=1;g_money+=15;set_status("HARVEST +$15");changed=1;}
        else set_status("NOT READY");
    }else{
        if(gid==12&&g_energy>=1){g_energy-=1;set_status("CROP WATERED");changed=1;}
        else set_status("WATER A CROP");
    }
    if(changed)spawn_action_fx(tx*TILE_SIZE+8,ty*TILE_SIZE+8,
        g_tool==TOOL_WATER?RGB565(80,170,255):RGB565(220,176,86));
    update_hud();
}

static void cycle_tool(){
    g_tool=(Tool)(((int)g_tool+1)&3);
    update_hud();set_status(tool_name());
}

static void set_inventory(int open){
    g_inventory_open=open?1:0;
    g_inventory.setVisible(g_inventory_open!=0);
    if(g_inventory_open){g_stage.setKeyboardFocus(&g_inventory_list);set_status("BAG OPEN");}
    else {g_stage.setKeyboardFocus(nullptr);set_status("BAG CLOSED");}
}

static void draw_world(){
    vxpe2d_fill_rect(g_frame,SCREEN_W,SCREEN_H,0,0,SCREEN_W,SCREEN_H,RGB565(65,104,52));
    g_batch.begin(g_frame,SCREEN_W,SCREEN_H);
    g_map_renderer.setAnimationTime((uint32_t)g_day_ms);
    g_map_renderer.render(g_map,g_atlas,g_batch);

    for(int i=0;i<3;++i){
        char name[20];snprintf(name,sizeof(name),"animal_%02d",i+1);
        const AtlasRegion* ar=g_atlas.findRegion(name);
        if(ar)g_batch.draw(ar->region,g_animal_x[i]-8,g_animal_y[i]-12,16,16,
                           0xFFFFu,255,VXPE_BLEND_ALPHA,false,false,(int16_t)g_animal_y[i]);
    }

    TextureRegion pr;
    if(g_walk_ticks>0)pr=g_walk[(int)g_dir].getKeyFrame();
    else {
        const AtlasRegion* idle=g_atlas.getRegion((uint16_t)(30+(int)g_dir*5));
        if(idle)pr=idle->region;
    }
    if(pr.texture())g_batch.draw(pr,g_player_x-12,g_player_y-20,24,24,
                                 0xFFFFu,255,VXPE_BLEND_ALPHA,false,false,(int16_t)g_player_y);
    g_batch.end();
    vxpe_particles_draw(&g_particles,g_frame,SCREEN_W,SCREEN_H);

    g_stage.draw(g_frame,SCREEN_W,SCREEN_H);
}

static void present(){
    VMUINT16* out=layer_buffer();if(!out)return;
    int sw=vm_graphic_get_screen_width(),sh=vm_graphic_get_screen_height();
    if(sw==SCREEN_W&&sh==SCREEN_H)memcpy(out,g_frame,sizeof(g_frame));
    else {
        vxpe2d_fill_rect((uint16_t*)out,sw,sh,0,0,sw,sh,RGB565(12,23,15));
        int cw=sw<SCREEN_W?sw:SCREEN_W,ch=sh<SCREEN_H?sh:SCREEN_H;
        for(int y=0;y<ch;++y)memcpy(out+y*sw,g_frame+y*SCREEN_W,cw*2);
    }
    vm_graphic_flush_layer(&g_layer,1);
}

static void draw_game(){if(g_layer<0||!g_started)return;draw_world();present();}

static void update_game(){
    g_day_ms+=33;g_anim_ms+=33;
    if(g_walk_ticks>0){g_walk[(int)g_dir].update(33);--g_walk_ticks;}
    else g_walk[(int)g_dir].reset();
    vxpe_particles_update(&g_particles,33);
    g_stage.act(0.033f);
    if((g_day_ms%330)==0)update_hud();
}

static void tick(VMINT){update_game();draw_game();}

static void start(){
    if(!g_started){
        setup_ui();
        if(!load_game_assets()){set_status("ASSET LOAD ERROR");return;}
        update_camera();g_started=1;
    }
    if(g_layer<0)g_layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);
    if(g_timer<0)g_timer=vm_create_timer(33,tick);
    draw_game();
}

static void stop(){
    if(g_timer>=0){vm_delete_timer(g_timer);g_timer=-1;}
    if(g_layer>=0){vm_graphic_delete_layer(g_layer);g_layer=-1;}
}

extern "C" void handle_keyevt(VMINT event,VMINT key){
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(g_inventory_open){
        if(key==VM_KEY_UP||key==VM_KEY_NUM2)g_inventory_list.selectPrevious();
        else if(key==VM_KEY_DOWN||key==VM_KEY_NUM8)g_inventory_list.selectNext();
        else if(key==VM_KEY_OK||key==VM_KEY_NUM5)g_inventory_list.activateSelection();
        else if(key==VM_KEY_NUM1||key==VM_KEY_RIGHT_SOFTKEY||key==VM_KEY_BACK)set_inventory(0);
        draw_game();return;
    }
    if(key==VM_KEY_LEFT||key==VM_KEY_NUM4)move_player(-5,0);
    else if(key==VM_KEY_RIGHT||key==VM_KEY_NUM6)move_player(5,0);
    else if(key==VM_KEY_UP||key==VM_KEY_NUM2)move_player(0,-5);
    else if(key==VM_KEY_DOWN||key==VM_KEY_NUM8)move_player(0,5);
    else if(key==VM_KEY_OK||key==VM_KEY_NUM5)interact();
    else if(key==VM_KEY_NUM0)cycle_tool();
    else if(key==VM_KEY_NUM1)set_inventory(1);
    else if(key==VM_KEY_RIGHT_SOFTKEY||key==VM_KEY_CLEAR||key==VM_KEY_BACK){vm_exit_app();return;}
    draw_game();
}

extern "C" void handle_penevt(VMINT event,VMINT x,VMINT y){
    if(g_inventory_open){
        if(event==VM_PEN_EVENT_TAP)g_stage.touchDown(x,y,0,0);
        else if(event==VM_PEN_EVENT_MOVE)g_stage.touchDragged(x,y,0);
        else if(event==VM_PEN_EVENT_RELEASE||event==VM_PEN_EVENT_ABORT)g_stage.touchUp(x,y,0,0);
        draw_game();
        return;
    }
    if(event!=VM_PEN_EVENT_TAP)return;
    if(y>=280){
        if(x<80)set_inventory(1);
        else if(x<160)cycle_tool();
        else interact();
        draw_game();
    }
}

extern "C" void handle_sysevt(VMINT msg,VMINT){
    if(msg==VM_MSG_CREATE||msg==VM_MSG_ACTIVE)start();
    else if(msg==VM_MSG_PAINT)draw_game();
    else if(msg==VM_MSG_INACTIVE)stop();
    else if(msg==VM_MSG_QUIT){stop();free_game_assets();vm_exit_app();}
}

extern "C" void vm_main(void){
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
