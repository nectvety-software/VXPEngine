// Runs the actual ARM VXP through VXPEmu's existing EmulatorCore.
#include "core/EmulatorCore.h"
#include "utils/Logger.h"
#include <QCoreApplication>
#include <QTimer>
#include <QDir>
#include <QFile>
#include <QTextStream>
#include <QImage>
#include <QSet>
#include <iostream>

int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    if(argc<3)return 2;
    const QString output=QString::fromLocal8Bit(argv[2]);
    QDir().mkpath(output);
    Logger::instance().setLogFile(output+"/runtime.log");
    EmulatorCore core;
    core.resizeDisplay(240,320);
    int frames=0,shots=0;
    bool pixels_ok=true;
    QString failure;
    QSet<quint64> hashes;
    QObject::connect(&core,&EmulatorCore::loadFailed,[&](const QString& s){failure=s;});
    QObject::connect(&core,&EmulatorCore::frameReady,[&](const QImage&){++frames;});
    auto capture=[&](const char* name) {
        QImage frame=core.lastFrame();
        if(frame.isNull())return;
        // Require native portrait dimensions and a rendered right edge.
        if(frame.width()!=240 || frame.height()!=320 || qRed(frame.pixel(239,150))==0 &&
            qGreen(frame.pixel(239,150))==0 && qBlue(frame.pixel(239,150))==0) pixels_ok=false;
        if(QString::fromLatin1(name)=="02_terrace" && argc>3) {
            QImage expected(QString::fromLocal8Bit(argv[3]));
            if(expected.isNull())pixels_ok=false;
            else for(int y=130;y<160;y+=5) for(int x=210;x<240;x+=5) {
                QRgb actual=frame.pixel(x,y),source=expected.pixel(x,y);
                // RGB565 round-trip can differ by <=8/4/8 from source PNG.
                if(qAbs(qRed(actual)-qRed(source))>8 || qAbs(qGreen(actual)-qGreen(source))>4 ||
                    qAbs(qBlue(actual)-qBlue(source))>8) pixels_ok=false;
            }
        }
        frame.save(output+"/"+name+".bmp");
        quint64 hash=1469598103934665603ULL;
        for(int y=0;y<frame.height();y+=4) for(int x=0;x<frame.width();x+=4)
            hash=(hash^(quint64)frame.pixel(x,y))*1099511628211ULL;
        hashes.insert(hash);++shots;
    };
    auto tap=[&](int ms,int key) {
        QTimer::singleShot(ms,&app,[&,key](){
            core.pressKey(key);
            QTimer::singleShot(120,&app,[&,key](){core.releaseKey(key);});
        });
    };
    core.loadApplication(QString::fromLocal8Bit(argv[1]));core.start();
    QTimer::singleShot(2200,&app,[&](){capture("01_library_dialogue");});
    tap(3000,48); // 0: terrace, clears dialogue.
    QTimer::singleShot(4400,&app,[&](){capture("02_terrace");});
    tap(5000,55);tap(6100,55);tap(7200,55); // 7: three spells.
    QTimer::singleShot(8100,&app,[&](){capture("03_duel");});
    tap(8500,48); // village
    QTimer::singleShot(10600,&app,[&](){capture("04_village_fire");});
    tap(11000,55); // cleanse center seal
    QTimer::singleShot(12000,&app,[&](){capture("05_ward");});
    tap(12400,57); // pause
    QTimer::singleShot(13800,&app,[&](){capture("06_pause");});
    tap(14500,57);tap(15000,49); // resume, restart
    QTimer::singleShot(17400,&app,[&](){capture("07_restart");});
    QTimer::singleShot(18000,&app,&QCoreApplication::quit);
    app.exec();
    QImage final=core.lastFrame();
    bool ok=failure.isEmpty() && core.state()==EmulatorCore::State::Running &&
        final.width()==240 && final.height()==320 && pixels_ok && shots==7 && hashes.size()>=5 && frames>15;
    core.stop();
    QFile report(output+"/report.txt");
    if(report.open(QIODevice::WriteOnly|QIODevice::Text)) {
        QTextStream out(&report);
        out<<"ARM VXP via VXPEmu EmulatorCore\nviewport=240x320\nframes="<<frames
           <<"\nshots="<<shots<<"\ndistinctShotHashes="<<hashes.size()
           <<"\nloadError="<<failure<<"\nbackgroundPixelParity="<<(pixels_ok?"PASS":"FAIL")
           <<"\nresult="<<(ok?"PASS":"FAIL")<<"\n";
    }
    std::cout<<(ok?"PASS":"FAIL")<<": ARM load, portrait framebuffer, numeric input, scenes, casts, pause/restart; frames="<<frames<<std::endl;
    return ok?0:1;
}
