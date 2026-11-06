#!/usr/bin/env python3
"""Cat's Pac-Man Arcade 0.1 — standalone arcade-style maze game.
Original procedural artwork and synthesized audio; no ROM or copyrighted assets.
Requires pygame-ce. Run: python cats_pacman_arcade_0.1.py
Test: python cats_pacman_arcade_0.1.py --autotest
"""
import os, sys, math, random, array
if '--autotest' in sys.argv:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
try:
    import pygame
except ImportError:
    sys.exit('Install pygame-ce first: python -m pip install pygame-ce')

TITLE = "Cat's PAC-MAN Arcade 0.1.1a | AC Kondo 1999-2026"
TILE = 8
MAP = [
'############################',
'#............##............#',
'#.####.#####.##.#####.####.#',
'#o####.#####.##.#####.####o#',
'#.####.#####.##.#####.####.#',
'#..........................#',
'#.####.##.########.##.####.#',
'#.####.##.########.##.####.#',
'#......##....##....##......#',
'######.##### ## #####.######',
'     #.##### ## #####.#     ',
'     #.##          ##.#     ',
'     #.## ###--### ##.#     ',
'######.## #      # ##.######',
'      .   #      #   .      ',
'######.## #      # ##.######',
'     #.## ######## ##.#     ',
'     #.##          ##.#     ',
'     #.## ######## ##.#     ',
'######.## ######## ##.######',
'#............##............#',
'#.####.#####.##.#####.####.#',
'#o..##.......  .......##..o#',
'###.##.##.########.##.##.###',
'#......##....##....##......#',
'#.##########.##.##########.#',
'#..........................#',
'############################',
]
assert len(MAP) == 28 and all(len(r) == 28 for r in MAP)
W, H = 224, 288
OX, OY = 0, 28
FPS = 60
YELLOW=(255,224,0); BLUE=(22,56,244); BLACK=(0,0,0); WHITE=(250,250,250)
RED=(255,40,54); PINK=(255,171,215); CYAN=(0,235,235); ORANGE=(255,177,55)
DIRS=((1,0),(0,1),(-1,0),(0,-1))

def center(cell): return (cell[0]*TILE+TILE//2, cell[1]*TILE+TILE//2)
def legal(x,y):
    if x<0 or x>=28: return y==14
    if y<0 or y>=28: return False
    return MAP[y][x] not in '#-'

def walkable(x,y,ghost=False):
    if x<0 or x>=28: return y==14
    if not (0<=y<28):return False
    if MAP[y][x]=='#':return False
    return ghost or MAP[y][x]!='-'

def neighbors(c,ghost=False):
    x,y=c
    return [d for d in DIRS if walkable(x+d[0],y+d[1],ghost)]

def sound(freq=400, duration=.1, kind='square', vol=.2, end=None):
    rate=22050; a=array.array('h'); n=int(rate*duration); phase=0
    for i in range(n):
        t=i/max(1,n-1); f=freq+(end-freq)*t if end is not None else freq
        phase+=f/rate
        p=phase%1
        if kind=='sine': wave=math.sin(2*math.pi*p)
        elif kind=='triangle': wave=4*abs(p-.5)-1
        elif kind=='noise': wave=random.uniform(-1,1)
        else: wave=1 if p<.5 else -1
        envelope=min(1, i/100)*((1-t)**.6)
        a.append(int(max(-1,min(1,wave*vol*envelope))*32767))
    return pygame.mixer.Sound(buffer=a.tobytes())

class Audio:
    def __init__(self):
        self.enabled=False; self.muted=False; self.sounds={}
        try:
            if pygame.mixer.get_init(): pygame.mixer.quit()
            pygame.mixer.init(22050,-16,1,512)
            self.sounds={
                'waka1':sound(510,.065,'triangle',.24,end=350),
                'waka2':sound(350,.065,'triangle',.24,end=510),
                'power':sound(180,.15,'square',.14,end=280),
                'ghost':sound(700,.27,'sine',.23,end=1150),
                'death':sound(780,.9,'triangle',.25,end=95),
                'fruit':sound(880,.24,'sine',.2,end=1250),
                'start':sound(460,.45,'triangle',.2,end=900),
            }
            self.enabled=True
        except pygame.error: pass
    def play(self,name):
        if self.enabled and not self.muted: self.sounds[name].play()

class Actor:
    def __init__(self, cell, direction=(-1,0), speed=1):
        self.x,self.y=center(cell); self.direction=direction; self.want=direction; self.speed=speed; self.ghost=False
    @property
    def cell(self): return (int(round((self.x-4)/8))%28,int(round((self.y-4)/8)))
    def aligned(self): return (self.x-4)%8==0 and (self.y-4)%8==0
    def move(self):
        if self.aligned():
            c=self.cell
            if self.want in neighbors(c,self.ghost): self.direction=self.want
            if self.direction not in neighbors(c,self.ghost): return
        self.x=(self.x+self.direction[0]*self.speed)%W
        self.y+=self.direction[1]*self.speed

class Game:
    def __init__(self, test=False):
        pygame.init()
        self.test=test
        self.screen=pygame.display.set_mode((W*3,H*3))
        pygame.display.set_caption(TITLE)
        self.canvas=pygame.Surface((W,H))
        self.clock=pygame.time.Clock()
        self.font=pygame.font.SysFont('arial',11,bold=True)
        self.small=pygame.font.SysFont('arial',9,bold=True)
        self.audio=Audio()
        self.high=0; self.frame=0; self.mode_frame=0; self.last_mode=None; self.paused=False; self.state='title'; self.level=1; self.score=0; self.lives=3; self.menu_frame=0
        self.new_level()
    def new_level(self):
        self.pellets={(x,y) for y,row in enumerate(MAP) for x,ch in enumerate(row) if ch in '.o'}
        self.power={(x,y) for y,row in enumerate(MAP) for x,ch in enumerate(row) if ch=='o'}
        self.reset_positions()
        self.fruit=None; self.fruit_timer=0
    def reset_positions(self):
        self.player=Actor((13,22),(-1,0))
        starts=[(13,11),(14,13),(13,14),(15,14)]
        self.ghosts=[Actor(c,DIRS[i],1) for i,c in enumerate(starts)]
        for g in self.ghosts:g.ghost=True
        self.ghost_release=[0,100,200,300]
        self.ghost_eaten=[False]*4
        self.mode_frame=0;self.last_mode=None
        self.fright=0; self.ghost_combo=0; self.ready=65;self.dots_eaten=0
    def begin(self):
        self.score=0; self.level=1; self.lives=3; self.state='play'; self.paused=False
        self.new_level(); self.audio.play('start')
    def die(self):
        self.audio.play('death'); self.lives-=1
        if self.lives<=0:
            self.state='gameover'; self.high=max(self.high,self.score)
        else: self.reset_positions(); self.ready=90
    def add(self,n):
        old=self.score; self.score+=n; self.high=max(self.high,self.score)
        if old<10000<=self.score: self.lives+=1
    def ghost_mode(self):
        # Approximate original scatter/chase schedule, with a persistent final chase.
        phases=(420,1200,420,1200,300,1200,300)
        t=self.mode_frame
        for j,length in enumerate(phases):
            if t<length:return 'scatter' if j%2==0 else 'chase'
            t-=length
        return 'chase'
    def choose_ghost(self, ghost, i):
        if not ghost.aligned():return
        opts=neighbors(ghost.cell,True)
        if not opts:return
        reverse=(-ghost.direction[0],-ghost.direction[1])
        forward=[d for d in opts if d!=reverse]
        if forward:opts=forward
        if self.fright and not self.ghost_eaten[i]:
            ghost.want=random.choice(opts);return
        px,py=self.player.cell
        if self.ghost_eaten[i]:target=(13,14)
        elif self.ghost_mode()=='scatter':target=[(25,0),(2,0),(27,27),(0,27)][i]
        elif i==0:target=(px,py)
        elif i==1:target=(px+4*self.player.direction[0],py+4*self.player.direction[1])
        elif i==2:
            bx,by=self.ghosts[0].cell
            ax=px+2*self.player.direction[0];ay=py+2*self.player.direction[1]
            target=(2*ax-bx,2*ay-by)
        else:target=(1,27) if (ghost.cell[0]-px)**2+(ghost.cell[1]-py)**2<64 else (px,py)
        # Arcade direction tie break: up, left, down, right.
        priority=((0,-1),(-1,0),(0,1),(1,0))
        ghost.want=min(opts,key=lambda d:((ghost.cell[0]+d[0]-target[0])**2+(ghost.cell[1]+d[1]-target[1])**2,priority.index(d)))
    def update(self):
        self.frame+=1
        if self.state=='title':self.menu_frame+=1;return
        if self.state!='play' or self.paused:return
        if self.ready>0:self.ready-=1;return
        keys=pygame.key.get_pressed()
        for key,d in ((pygame.K_LEFT,(-1,0)),(pygame.K_RIGHT,(1,0)),(pygame.K_UP,(0,-1)),(pygame.K_DOWN,(0,1)),(pygame.K_a,(-1,0)),(pygame.K_d,(1,0)),(pygame.K_w,(0,-1)),(pygame.K_s,(0,1))):
            if keys[key]:self.player.want=d
        if self.test:self.player.want=random.choice(neighbors(self.player.cell) or [self.player.direction]) if self.player.aligned() else self.player.want
        self.player.move()
        pc=self.player.cell
        if self.player.aligned() and pc in self.pellets:
            self.pellets.remove(pc)
            self.dots_eaten+=1
            if pc in self.power:
                self.power.remove(pc);self.add(50);self.fright=420;self.ghost_combo=0;self.audio.play('power')
            else:
                self.add(10)
                if self.frame%3==0:self.audio.play('waka1' if self.frame%2 else 'waka2')
            if self.dots_eaten in (70,170):self.fruit=(13,17);self.fruit_timer=570
            if not self.pellets:
                self.level+=1;self.new_level();return
        if self.fruit_timer:self.fruit_timer-=1
        else:self.fruit=None
        if self.fruit and pc==self.fruit:
            self.add([100,300,500,700,1000,2000,3000,5000][min(self.level-1,7)]);self.audio.play('fruit');self.fruit=None
        if self.fright:self.fright-=1
        else:self.mode_frame+=1
        mode=self.ghost_mode()
        if self.last_mode is not None and mode!=self.last_mode:
            for g in self.ghosts:g.direction=(-g.direction[0],-g.direction[1]);g.want=g.direction
        self.last_mode=mode
        for i,g in enumerate(self.ghosts):
            if self.frame < self.ghost_release[i]:continue
            if self.frame%(3 if self.fright and not self.ghost_eaten[i] else 2)==0:
                self.choose_ghost(g,i)
                g.move()
            if self.ghost_eaten[i] and g.cell==(13,14):self.ghost_eaten[i]=False
            if abs(self.player.x-g.x)<7 and abs(self.player.y-g.y)<7:
                if self.fright:
                    self.ghost_combo+=1;self.add(200*2**min(3,self.ghost_combo-1))
                    self.audio.play('ghost');self.ghost_eaten[i]=True;g.direction=(-g.direction[0],-g.direction[1])
                else:self.die();return
    def draw_maze(self):
        s=self.canvas
        for y,row in enumerate(MAP):
            for x,ch in enumerate(row):
                px,py=x*TILE,OY+y*TILE
                if ch=='#':
                    # rounded-looking double-line walls, exposing only open edges
                    pygame.draw.rect(s,BLUE,(px+1,py+1,6,6),border_radius=2)
                    pygame.draw.rect(s,BLACK,(px+3,py+3,2,2))
                elif ch=='-':pygame.draw.line(s,PINK,(px,py+4),(px+8,py+4),2)
        for x,y in self.pellets:
            px,py=center((x,y));py+=OY
            if (x,y) in self.power:
                if self.frame//12%2==0:pygame.draw.circle(s,(255,196,180),(px,py),3)
            else:pygame.draw.circle(s,(255,195,160),(px,py),1)
    def draw_pac(self):
        s=self.canvas; x=self.player.x;y=self.player.y+OY
        mouth=7+int(31*abs(math.sin(self.frame*.15)))
        angle={(-1,0):180,(1,0):0,(0,-1):90,(0,1):270}[self.player.direction]
        pts=[(x,y)]
        for k in range(25):
            a=math.radians(angle+mouth+(360-2*mouth)*k/24)
            pts.append((x+7*math.cos(a),y-7*math.sin(a)))
        pygame.draw.polygon(s,YELLOW,pts)
    def draw_ghost(self,g,i):
        x,y=int(g.x),int(g.y+OY)
        color=[RED,PINK,CYAN,ORANGE][i]
        if self.ghost_eaten[i]:color=BLACK
        elif self.fright:color=(25,45,240) if self.fright>100 or self.frame//10%2 else WHITE
        pygame.draw.circle(self.canvas,color,(x,y-2),7)
        pygame.draw.rect(self.canvas,color,(x-7,y-2,14,9))
        for dx in (-5,0,5):pygame.draw.circle(self.canvas,color,(x+dx,y+7),2)
        for dx in (-3,3):
            pygame.draw.ellipse(self.canvas,WHITE,(x+dx-2,y-5,5,7))
            if not self.fright or self.ghost_eaten[i]:pygame.draw.circle(self.canvas,(10,40,220),(x+dx+g.direction[0],y-2+g.direction[1]),2)
            else:pygame.draw.circle(self.canvas,WHITE,(x+dx,y-1),1)
    def text(self,msg,x,y,color=WHITE,font=None):
        self.canvas.blit((font or self.font).render(str(msg),False,color),(x,y))
    def draw(self):
        self.canvas.fill(BLACK)
        self.text('1UP',16,3);self.text('HIGH SCORE',82,3)
        self.text(f'{self.score:06d}',16,15);self.text(f'{self.high:06d}',93,15)
        self.draw_maze()
        if self.fruit:pygame.draw.circle(self.canvas,RED,(108,OY+140),5)
        if self.state!='title':
            self.draw_pac()
            for i,g in enumerate(self.ghosts):self.draw_ghost(g,i)
        for i in range(max(0,self.lives-1)):
            pygame.draw.circle(self.canvas,YELLOW,(14+i*16,263),6)
        pygame.draw.circle(self.canvas,RED,(190,263),5)
        self.text('CAT ARCADE 0.1.1a',70,273,YELLOW,self.small)
        if self.state=='title':
            # Classic arcade-inspired ghost roll call: each character enters in sequence.
            self.text('CHARACTER / NICKNAME',34,46,CYAN,self.small)
            names=(('SHADOW','BLINKY',RED),('SPEEDY','PINKY',PINK),
                   ('BASHFUL','INKY',CYAN),('POKEY','CLYDE',ORANGE))
            for i,(character,nickname,color) in enumerate(names):
                elapsed=self.menu_frame-i*36
                if elapsed<0:continue
                y=69+i*31
                self.text(f'"{character}"',17,y,color,self.small)
                self.text(f'"{nickname}"',116,y,color,self.small)
                gx=min(103, -12+elapsed*3)
                # Draw a ghost without changing game state.
                ghost=Actor((0,0));ghost.x=gx;ghost.y=y-OY+12
                self.draw_ghost(ghost,i)
            self.text('PAC-MAN',82,206,YELLOW)
            if self.menu_frame//30%2==0:
                self.text('PRESS ENTER TO START',47,226,WHITE,self.small)
            self.text('ARROWS / WASD TO MOVE',51,241,CYAN,self.small)
        elif self.state=='gameover':self.text('GAME OVER',78,146,RED)
        elif self.paused:self.text('PAUSED',91,146,YELLOW)
        elif self.ready:self.text('READY!',90,146,YELLOW)
        screen_size=self.screen.get_size()
        scale=max(1,min(screen_size[0]//W,screen_size[1]//H))
        size=(W*scale,H*scale)
        self.screen.fill(BLACK)
        self.screen.blit(pygame.transform.scale(self.canvas,size),((screen_size[0]-size[0])//2,(screen_size[1]-size[1])//2))
        pygame.display.flip()
    def run(self):
        count=0;running=True
        if self.test:self.begin()
        while running:
            for e in pygame.event.get():
                if e.type==pygame.QUIT:running=False
                elif e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_ESCAPE:running=False
                    elif e.key in (pygame.K_RETURN,pygame.K_SPACE) and self.state!='play':self.begin()
                    elif e.key==pygame.K_p:self.paused=not self.paused
                    elif e.key==pygame.K_m:self.audio.muted=not self.audio.muted
                    elif e.key==pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                    elif e.key in (pygame.K_UP,pygame.K_DOWN,pygame.K_LEFT,pygame.K_RIGHT,pygame.K_w,pygame.K_a,pygame.K_s,pygame.K_d):
                        self.player.want={pygame.K_UP:(0,-1),pygame.K_w:(0,-1),pygame.K_DOWN:(0,1),pygame.K_s:(0,1),pygame.K_LEFT:(-1,0),pygame.K_a:(-1,0),pygame.K_RIGHT:(1,0),pygame.K_d:(1,0)}[e.key]
            self.update();self.draw();count+=1
            if self.test and count>=300:break
            self.clock.tick(FPS)
        pygame.quit()
        if self.test:print(f'autotest passed: {count} frames, score {self.score}')

if __name__=='__main__':Game('--autotest' in sys.argv).run()
