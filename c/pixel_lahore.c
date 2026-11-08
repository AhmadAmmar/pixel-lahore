/* Pixel Lahore in C: the same Badshahi Masjid, drawn the low-level way.
 *
 * No libraries beyond the C standard library. The screen is an array of bytes in memory
 * (a framebuffer); each byte is a palette index, as on 8-bit machines and in graphics.h's
 * 16-colour modes. Functions are named after the old BGI ones (putpixel, line, circle,
 * bar) so the mapping is clear. Frames are written as PPM images, the simplest picture
 * format there is: a short text header and then raw red, green, blue bytes.
 *
 *     gcc -O2 -o pixel_lahore pixel_lahore.c -lm
 *     ./pixel_lahore            writes frames/frame_000.ppm ... and still.ppm
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define W 160
#define H 120
#define GROUND 104
#define NFRAMES 120

static unsigned char fb[H][W];          /* the framebuffer */
static int colour = 15;                  /* current drawing colour, as setcolor() in graphics.h */

static const unsigned char PALETTE[16][3] = {
    {16, 20, 43},   {29, 43, 83},   {94, 58, 110},  {90, 150, 210}, {170, 210, 235}, {240, 140, 60},
    {255, 220, 110}, {240, 236, 225}, {190, 185, 175}, {170, 62, 45}, {115, 38, 32},  {40, 20, 22},
    {70, 120, 60},  {40, 75, 40},   {200, 150, 110}, {12, 10, 14}};
static const int BAYER[4][4] = {{0, 8, 2, 10}, {12, 4, 14, 6}, {3, 11, 1, 9}, {15, 7, 13, 5}};

/* ------------------------------------------------------------ primitives */
void setcolor(int c) { colour = c; }

void putpixel(int x, int y, int c) {
    if (x >= 0 && x < W && y >= 0 && y < H) fb[y][x] = (unsigned char)c;
}

void bar(int x0, int y0, int x1, int y1) {          /* filled rectangle, x0 <= x < x1 */
    for (int y = y0; y < y1; y++)
        for (int x = x0; x < x1; x++) putpixel(x, y, colour);
}

void line(int x0, int y0, int x1, int y1) {          /* Bresenham: integer steps only */
    int dx = abs(x1 - x0), dy = -abs(y1 - y0);
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
    for (;;) {
        putpixel(x0, y0, colour);
        if (x0 == x1 && y0 == y1) return;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void circle(int cx, int cy, int r) {                  /* midpoint circle: eight symmetric points per step */
    int x = r, y = 0, err = 1 - r;
    while (x >= y) {
        int px[8] = {x, y, -y, -x, -x, -y, y, x}, py[8] = {y, x, x, y, -y, -x, -x, -y};
        for (int i = 0; i < 8; i++) putpixel(cx + px[i], cy + py[i], colour);
        y++;
        if (err < 0) err += 2 * y + 1;
        else { x--; err += 2 * (y - x) + 1; }
    }
}

void fillcircle(int cx, int cy, int r) {
    for (int y = -r; y <= r; y++)
        for (int x = -r; x <= r; x++)
            if (x * x + y * y <= r * r) putpixel(cx + x, cy + y, colour);
}

/* ------------------------------------------------------------ shapes as inside tests */
static int in_arch(double x, double y, double cx, double spring, double bottom, double w) {
    double off = 0.25 * w, r = w / 2 + off;          /* two centres, k = 0.5 */
    if (y >= spring) return fabs(x + 0.5 - cx) <= w / 2 && y < bottom;
    double a = (x - cx - off) * (x - cx - off) + (y - spring) * (y - spring);
    double b = (x - cx + off) * (x - cx + off) + (y - spring) * (y - spring);
    return a <= r * r && b <= r * r;
}

void arch(double cx, double spring, double bottom, double w, double frame, int inner) {
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            if (in_arch(x, y, cx, spring, bottom, w + 2 * frame)) putpixel(x, y, 7);
            if (in_arch(x, y, cx, spring, bottom, w)) putpixel(x, y, inner);
        }
}

void dome(double cx, double base, double R, double h) {
    setcolor(9); bar((int)(cx - 0.8 * R), (int)base, (int)(cx + 0.8 * R), (int)base + 6);
    for (int y = 0; y < H; y++) {
        double u = (base - y) / h;
        if (u < 0 || u > 1) continue;
        double neck = 0.8 + 0.2 * fmin(u / 0.15, 1);
        double hw = R * pow(1 - u, 0.7) * (1 + 1.2 * u) * neck;
        for (int x = 0; x < W; x++)
            if (fabs(x - cx + 0.5) <= hw) putpixel(x, y, x > cx + 0.3 * R ? 8 : 7);
    }
    setcolor(6); line((int)cx, (int)(base - h), (int)cx, (int)(base - h - 5));
    fillcircle((int)cx, (int)(base - h - 2), 1);
}

void minaret(double x, double top, double w, int nbalc) {
    int x0 = (int)(x - w / 2), x1 = (int)(x + w / 2), bottom = GROUND - 8;
    setcolor(9); bar(x0, (int)top, x1, bottom);
    setcolor(10); bar(x1 - 2, (int)top, x1, bottom);
    setcolor(7);
    for (int y = (int)top + 3; y < bottom; y += 6) bar(x0, y, x1, y + 1);
    setcolor(8);
    for (int i = 1; i <= nbalc; i++) {
        int y = (int)(top + (bottom - top) * i / (nbalc + 1.0));
        bar(x0 - 1, y, x1 + 1, y + 2);
    }
    bar(x0 - 1, (int)top - 1, x1 + 1, (int)top + 1);
    setcolor(7); bar(x0, (int)top - 5, x0 + 1, (int)top - 1); bar(x1 - 1, (int)top - 5, x1, (int)top - 1);
    for (int y = (int)top - 10; y <= (int)top - 5; y++) {           /* the chhatri dome */
        double u = (top - 5 - y) / 5.0, hw = (w / 2 + 0.5) * pow(1 - u, 0.7) * (1 + 1.2 * u);
        for (int xx = x0 - 2; xx <= x1 + 2; xx++)
            if (fabs(xx - x + 0.5) <= hw) putpixel(xx, y, 7);
    }
    setcolor(6); line((int)x, (int)top - 11, (int)x, (int)top - 13);
}

void block(int x0, int y0, int x1, int y1) {
    setcolor(9); bar(x0, y0, x1, y1);
    setcolor(7); bar(x0, y0, x1, y0 + 1);
    setcolor(9);
    for (int x = x0; x < x1; x += 3) bar(x, y0 - 2, x + 2, y0);
}

/* the mosque: every left-hand part is drawn again at its mirror position W - x */
void badshahi(void) {
    for (int s = 0; s < 2; s++) {
        double m = s ? -1 : 1, o = s ? W : 0;            /* x -> o + m*x mirrors when s = 1 */
        minaret(o + m * 14, 24, 7, 3);
        dome(o + m * 46, 52, 9, 16);
    }
    dome(80, 38, 13, 22);
    for (int s = 0; s < 2; s++) {
        double m = s ? -1 : 1, o = s ? W : 0;
        block(s ? W - 66 : 30, 60, s ? W - 30 : 66, GROUND - 8);
        minaret(o + m * 30, 44, 4, 1);
        arch(o + m * 40, 76, GROUND - 8, 6, 2, 11);
        arch(o + m * 54, 76, GROUND - 8, 6, 2, 11);
    }
    block(64, 42, 96, GROUND - 8);
    arch(80, 62, GROUND - 8, 20, 3, 11);
    arch(80, 70, GROUND - 8, 10, 1, 10);
}

/* ------------------------------------------------------------ sky and light */
void sky(double elev) {
    int top = 0, bottom = 1;
    if (elev > 0.25) { top = 3; bottom = 4; }
    else if (elev > 0) { top = 2; bottom = 5; }
    else if (elev > -0.2) { top = 0; bottom = 2; }
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            fb[y][x] = (double)y / GROUND > BAYER[y % 4][x % 4] / 16.0 ? bottom : top;
    if (elev < 0) {
        srand(7);                                         /* same stars every frame */
        for (int i = 0; i < 40; i++) { int x = rand() % W, y = rand() % 60; putpixel(x, y, 7); }
    }
}

void ground(void) {
    setcolor(14); bar(0, GROUND - 8, W, GROUND);
    setcolor(7); bar(0, GROUND - 8, W, GROUND - 7);
    for (int y = GROUND; y < H; y++)
        for (int x = 0; x < W; x++)
            fb[y][x] = (x - 80) * (x - 80) * 0.02 < (y - GROUND + 2) ? 14 : 12;
}

void night(unsigned char before[H][W]) {               /* palette swap on whatever the mosque covered */
    static const int swap[16] = {0, 1, 2, 3, 4, 5, 6, 8, 10, 10, 11, 11, 13, 13, 2, 15};
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
            if (fb[y][x] != before[y][x] || y >= GROUND - 8) fb[y][x] = (unsigned char)swap[fb[y][x]];
}

/* ------------------------------------------------------------ kite physics */
typedef struct { double x, y, vx, vy; } Body;

void kite_step(Body *k, double t, double dt) {
    const double ax = 4, ay = GROUND - 2, m = 1, g = 20, ks = 6, L0 = 90, drag = 1.5;
    double wx = 10 + 4 * sin(0.7 * t) + 2 * sin(2.3 * t), wy = -30 - 3 * sin(1.3 * t);
    double dx = k->x - ax, dy = k->y - ay, L = sqrt(dx * dx + dy * dy);
    double stretch = L > L0 ? L - L0 : 0;                 /* a string pulls but never pushes */
    double fx = -ks * stretch * dx / L + drag * (wx - k->vx);
    double fy = m * g - ks * stretch * dy / L + drag * (wy - k->vy);
    k->vx += fx / m * dt; k->vy += fy / m * dt;           /* semi-implicit Euler */
    k->x += k->vx * dt;   k->y += k->vy * dt;
}

void draw_kite(const Body *k) {
    setcolor(15); line(4, GROUND - 2, (int)k->x, (int)k->y);
    for (int y = -4; y <= 4; y++)
        for (int x = -3; x <= 3; x++)
            if (fabs(x) / 3 + fabs(y) / 4 <= 1) putpixel((int)k->x + x, (int)k->y + y, x > 0 ? 6 : 5);
}

/* ------------------------------------------------------------ output */
void save_ppm(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    fprintf(f, "P6\n%d %d\n255\n", W, H);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) fwrite(PALETTE[fb[y][x]], 1, 3, f);
    fclose(f);
}

void render(double phase, const Body *k) {
    static unsigned char before[H][W];
    double a = 2 * M_PI * phase, elev = sin(a);
    sky(elev);
    if (elev > -0.05) { setcolor(6); fillcircle((int)(80 - 84 * cos(a)), (int)(GROUND - 84 * elev), 6); }
    else { setcolor(7); fillcircle((int)(80 + 84 * cos(a)), (int)(GROUND + 84 * elev), 4); }
    ground();
    for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) before[y][x] = fb[y][x];
    badshahi();
    if (elev < 0) night(before);
    if (k) draw_kite(k);
}

int main(void) {
    Body k = {40, 40, 0, 0};
    char name[64];
    render(0.22, NULL);
    save_ppm("still.ppm");
    system("mkdir frames 2>nul || mkdir -p frames");
    for (int f = 0; f < NFRAMES; f++) {
        for (int s = 0; s < 8; s++) kite_step(&k, f / 10.0 + s / 80.0, 1 / 80.0);
        render(-0.05 + 1.1 * f / NFRAMES, &k);
        snprintf(name, sizeof name, "frames/frame_%03d.ppm", f);
        save_ppm(name);
    }
    printf("wrote still.ppm and %d frames; kite ended at (%.1f, %.1f)\n", NFRAMES, k.x, k.y);
    return 0;
}
