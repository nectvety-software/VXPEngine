#include "vxpgdx/StrategyRPG.h"
#include <cassert>
#include <cstdio>
#include <cstring>
using namespace vxpe::gdx;
using namespace vxpe::gdx::strategy;

int main(){
    LocalizationTable<8> loc;
    LocalizedEntry e{}; e.key="play"; e.text[(uint8_t)Locale::Vietnamese]="Choi"; e.text[(uint8_t)Locale::English]="Play";
    assert(loc.add(e)); assert(loc.size()==1); assert(std::strcmp(loc.get("play",Locale::English),"Play")==0);
    assert(std::strcmp(loc.get("play",Locale::Thai),"Play")==0);

    Utf8GlyphFont<8,16> font;
    assert(font.add('?',0,5));
    assert(font.add(0x1EBFu,1,7)); /* Vietnamese ế */
    assert(font.add(0x4E2Du,2,9)); /* Chinese 中 */
    assert(font.add(0xD55Cu,3,9)); /* Korean 한 */
    assert(font.add(0x0E44u,4,8)); /* Thai ไ */
    const char utf8[]="\xE1\xBA\xBF\xE4\xB8\xAD\xED\x95\x9C\xE0\xB9\x84";
    assert(font.textWidth(utf8)==33);

    ScreenStack<4> screens; assert(screens.push(1)); assert(screens.push(2,ScreenTransition::Fade,100));
    screens.update(50); assert(screens.current()->id==2); assert(screens.transitionAlpha()>=126&&screens.transitionAlpha()<=128);
    assert(screens.pop()); assert(screens.current()->id==1);

    StrategyGrid<8,8> grid; grid.configure(10,20,5,4,24,24); grid.setSelected(2,1);
    grid.setFlag(2,2,GridMove); grid.setFlag(3,2,GridAttack);
    assert(grid.flags(2,2)&GridMove); assert(grid.flags(3,2)&GridAttack);
    assert(grid.moveSelection(1,0)); assert(grid.selectedX()==3&&grid.selectedY()==1);

    WorldMap<8> map;
    assert(map.add({20,20,1,WorldNodeState::Cleared,3}));
    assert(map.add({40,30,2,WorldNodeState::Open,1}));
    assert(map.add({70,50,3,WorldNodeState::Locked,0}));
    assert(map.selectNextOpen(1)); assert(map.selected()==1);

    std::puts("VXPGDX_STRATEGY_RPG_PASS");
    return 0;
}
