#include "scene.h"
#include <assert.h>
#include <stdio.h>

static void save(const char* path,const uint16_t* p){FILE* f=fopen(path,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");for(int i=0;i<240*320;++i){uint16_t c=p[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);}
int main(){
  static PocketPitch g;
  assert(sizeof(g)<512);
  static uint16_t frame[240*320];g.draw(frame);save("pocket_pitch_title.ppm",frame);
  assert(g.mode==0&&g.best==0);
  g.loadBest(725);assert(g.best==725&&g.loadedBest);
  g.input(5);assert(g.mode==1&&g.serveTicks==20);
  for(int i=0;i<20;++i)g.update();assert(g.serveTicks==0&&g.ballVy<0);
  int before=g.ballY;g.update();assert(g.ballY<before);
  g.draw(frame);save("pocket_pitch_match.ppm",frame);
  g.input(9);int pausedY=g.ballY;g.update();assert(g.mode==2&&g.ballY==pausedY);
  g.input(9);assert(g.mode==1);
  g.ballX=120*256;g.ballY=44*256;g.ballVx=0;g.ballVy=-256;g.serveTicks=0;g.update();
  assert(g.goals==1&&g.score>=100&&g.serveTicks==20);
  g.serveTicks=0;g.ballX=120*256;g.ballY=48*256;g.ballVx=0;g.ballVy=-256;g.keeperX=120;g.update();assert(g.ballY==56*256&&g.combo==0);
  g.ballX=37*256;g.ballY=140*256;g.ballVx=-256;g.ballVy=0;g.update();assert(g.ballX==38*256&&g.ballVx>0);
  g.ballX=g.bumpers[2].x*256;g.ballY=(g.bumpers[2].y+10)*256;g.ballVx=0;g.ballVy=-256;g.serveTicks=0;int points=g.score;g.update();assert(g.score>points);
  g.input(1);assert(g.skillLeft==1&&g.skillCooldown>0);
  for(int i=0;i<75;++i)g.update();assert(g.skillCooldown==0);
  g.seconds=1;g.tick=29;g.update();assert(g.mode==3&&g.seconds==0);
  g.input(5);assert(g.mode==1&&g.goals==0);
  static uint16_t pixels[240*320+2];pixels[0]=pixels[240*320+1]=0x1234;g.draw(pixels+1);assert(pixels[0]==0x1234&&pixels[240*320+1]==0x1234);
  puts("PASS Pocket Pitch: 240x320 bounds, boot, launch, movement, pause, goal, bumper, curve cooldown, replay, bounded state");
}
