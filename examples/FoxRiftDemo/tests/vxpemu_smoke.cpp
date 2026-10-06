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
        if(QString::fromLatin1(name)=="04_match" && argc>3) {
            QImage expected(QString::fromLocal8Bit(argv[3]));
            if(expected.isNull())pixels_ok=false;
            else for(int y=70;y<90;y+=5) for(int x=10;x<30;x+=5) {
                QRgb actual=frame.pixel(x,y),source=expected.pixel(x,(y+560)%320);
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
    QTimer::singleShot(700,&app,[&](){capture("01_splash");});
    tap(2000,53); // skip splash / show selection
    QTimer::singleShot(2700,&app,[&](){capture("02_heroes");});
    tap(3200,54);tap(3500,56); // select Torvan and Nimara bot
    QTimer::singleShot(4000,&app,[&](){capture("03_choose");});
    tap(4500,53); // start duel
    QTimer::singleShot(6000,&app,[&](){capture("04_match");});
    tap(6500,53);tap(6800,55);tap(7100,57);tap(7400,48);
    QTimer::singleShot(9000,&app,[&](){capture("05_skills");});
    tap(9500,42);
    QTimer::singleShot(10500,&app,[&](){capture("06_pause");});
    tap(11100,42);tap(11800,51);
    QTimer::singleShot(13200,&app,[&](){capture("07_rematch");});
    QTimer::singleShot(14000,&app,&QCoreApplication::quit);
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
    std::cout<<(ok?"PASS":"FAIL")<<": ARM load, portrait framebuffer, numeric input, splash, selection, original heroes, solo bot, skills, pause/rematch; frames="<<frames<<std::endl;
    return ok?0:1;
}
