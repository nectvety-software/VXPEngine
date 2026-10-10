from pathlib import Path
p=Path('examples/FoxRiftDemo/tests/vxpemu_smoke.cpp');s=p.read_text().replace('QTimer::singleShot(20000,&app,&QCoreApplication::quit);','''tap(19500,35); // # opens equipment shop.
    QTimer::singleShot(20700,&app,[&](){capture("09_shop");});
    tap(21200,53); // buy selected starter blade.
    QTimer::singleShot(22200,&app,[&](){capture("10_bought");});
    tap(22800,35);
    QTimer::singleShot(23500,&app,[&](){core.pressKey(56);});
    QTimer::singleShot(27500,&app,[&](){core.releaseKey(56);});
    QTimer::singleShot(30500,&app,[&](){capture("11_wave_march");});
    QTimer::singleShot(32000,&app,&QCoreApplication::quit);''').replace('shots==8','shots==11');s=s.replace('world movement/scroll, pause/rematch; frames=','world movement/scroll, minions, shop/purchase, pause/rematch; frames=');p.write_text(s)
