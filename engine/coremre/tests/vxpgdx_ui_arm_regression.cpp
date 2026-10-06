#include "vxpgdx/VxpGdx.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>

using namespace vxpe::gdx;
using namespace vxpe::gdx::scene2d;
using namespace vxpe::gdx::scene2d::ui;

namespace {

int g_clicks=0;
int g_last=-1;

void onList(List<32>&,int index,const char*,void*){
    ++g_clicks;
    g_last=index;
}

} // namespace

int main(){
    static const char* kItems[]={
        "ITEM 00","ITEM 01","ITEM 02","ITEM 03","ITEM 04","ITEM 05","ITEM 06","ITEM 07",
        "ITEM 08","ITEM 09","ITEM 10","ITEM 11","ITEM 12","ITEM 13","ITEM 14","ITEM 15",
        "ITEM 16","ITEM 17","ITEM 18","ITEM 19","ITEM 20","ITEM 21","ITEM 22","ITEM 23",
        "ITEM 24","ITEM 25","ITEM 26","ITEM 27","ITEM 28","ITEM 29","ITEM 30","ITEM 31"
    };

    List<32> list;
    list.setCallback(onList,nullptr);
    for(const char* s:kItems)assert(list.addItem(s));
    assert(list.size()==32);
    assert(list.getPrefHeightPx()==32*18);

    ScrollPane pane;
    pane.setBounds(10,10,100,54);
    assert(pane.setWidget(list));

    Stage stage(120,100);
    assert(stage.addActor(pane));
    static uint16_t fb[120*100]{};

    stage.act(0.033f);
    stage.draw(fb,120,100);
    assert(pane.getMaxScrollYPixels()==32*18-54);
    assert(list.getLastDrawnRows()<=4);
    assert(list.getLastDrawnRows()>=3);

    // Tap stays delegated to the list.
    assert(stage.touchDown(20,10+18+5));
    stage.touchUp(20,10+18+5);
    assert(g_clicks==1&&g_last==1);

    // Drag cancels the child click and moves only the scroll pane.
    const int32_t before=pane.getScrollYPixels();
    assert(stage.touchDown(20,45));
    stage.touchDragged(20,18);
    stage.touchUp(20,18);
    assert(pane.getScrollYPixels()>before);
    assert(g_clicks==1);

    // Integer scroll clamps exactly.
    pane.setScrollPixels(0,99999);
    assert(pane.getScrollYPixels()==pane.getMaxScrollYPixels());
    pane.setScrollPixels(0,-50);
    assert(pane.getScrollYPixels()==0);

    // Visible-row culling remains bounded after scrolling.
    pane.setScrollPixels(0,18*20);
    stage.draw(fb,120,100);
    assert(list.getLastDrawnRows()<=4);

    puts("VXPGDX_UI_ARM_REGRESSION_PASS");
    return 0;
}
