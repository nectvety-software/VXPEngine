import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.*;

/**
 * AssetTool - sprite sheet pipeline for CungThuBongDen (MRE .vxp).
 *
 * Modes:
 *   slice  <sheet.png> <outdir>
 *       Auto-detects sprites via connected components (alpha or non-white),
 *       writes comp_<i>.png crops plus boxes.txt (idx x y w h) and a numbered
 *       contact sheet preview.png for manual identification.
 *
 *   build <manifest.txt> <outdir>
 *       Manifest line:  <name> <sheet.png> <x> <y> <w> <h> <outW> <outH> [opaque]
 *       Crops, box-filter resizes to outW x outH (nearest for upscale),
 *       converts to little-endian RGB565 followed by a 1-bit transparency
 *       mask (w*h/8 bytes, MSB first). Flag "opaque" skips the mask.
 *       Output: <outdir>/<name>.raw + sprites.h with dimension defines.
 */
public class AssetTool {

    static class Box {
        int x, y, w, h, area;
        Box(int x, int y, int w, int h, int area) { this.x = x; this.y = y; this.w = w; this.h = h; this.area = area; }
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: AssetTool slice <sheet.png> <outdir>\n" +
                               "       AssetTool build <manifest.txt> <outdir>");
            System.exit(2);
        }
        switch (args[0]) {
            case "slice": doSlice(args[1], args[2]); break;
            case "build": doBuild(args[1], args[2]); break;
            default: System.err.println("unknown mode " + args[0]); System.exit(2);
        }
    }

    // ------------------------------------------------------------------ slice
    static void doSlice(String sheetPath, String outdir) throws Exception {
        BufferedImage img = ImageIO.read(new File(sheetPath));
        int W = img.getWidth(), H = img.getHeight();
        boolean[] fg = new boolean[W * H];
        boolean hasAlpha = img.getColorModel().hasAlpha();
        for (int y = 0; y < H; y++) {
            for (int x = 0; x < W; x++) {
                int argb = img.getRGB(x, y);
                int a = (argb >>> 24) & 0xFF;
                int r = (argb >> 16) & 0xFF, g = (argb >> 8) & 0xFF, b = argb & 0xFF;
                int min = Math.min(r, Math.min(g, b)), max = Math.max(r, Math.max(g, b));
                // background is noisy near-white (AI sheets): light + low saturation
                boolean solid = !(a < 40) && !(min >= 224 && (max - min) <= 16);
                fg[y * W + x] = solid;
            }
        }
        // dilate 3px to merge parts of one sprite, label, then take tight boxes on original mask
        boolean[] dil = dilate(fg, W, H, 3);
        int[] label = new int[W * H];
        Map<Integer, Box> boxes = new HashMap<>();
        int[] stack = new int[W * H];
        int next = 1;
        for (int start = 0; start < W * H; start++) {
            if (!dil[start] || label[start] != 0) continue;
            int sp = 0;
            stack[sp++] = start;
            label[start] = next;
            int minx = W, miny = H, maxx = -1, maxy = -1;
            long area = 0;
            while (sp > 0) {
                int p = stack[--sp];
                int px = p % W, py = p / W;
                if (fg[p]) {
                    area++;
                    if (px < minx) minx = px;
                    if (py < miny) miny = py;
                    if (px > maxx) maxx = px;
                    if (py > maxy) maxy = py;
                }
                int[][] nb = {{px+1,py},{px-1,py},{px,py+1},{px,py-1}};
                for (int[] n : nb) {
                    int nx = n[0], ny = n[1];
                    if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
                    int q = ny * W + nx;
                    if (dil[q] && label[q] == 0) { label[q] = next; stack[sp++] = q; }
                }
            }
            if (area >= 250) {
                boxes.put(next, new Box(minx, miny, maxx - minx + 1, maxy - miny + 1, (int) area));
            }
            next++;
        }
        java.util.List<Box> list = new ArrayList<>(boxes.values());
        list.sort(Comparator.comparingInt((Box b) -> b.y / 40).thenComparingInt(b -> b.x));
        new File(outdir).mkdirs();
        PrintWriter pw = new PrintWriter(new FileWriter(outdir + File.separator + "boxes.txt"));
        int i = 0;
        BufferedImage contact = new BufferedImage(W, H, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g2 = contact.createGraphics();
        g2.drawImage(img, 0, 0, null);
        g2.setColor(new Color(255, 0, 0, 160));
        Font f = new Font("Monospaced", Font.BOLD, 22);
        g2.setFont(f);
        for (Box b : list) {
            pw.printf(Locale.ROOT, "%d %d %d %d %d%n", i, b.x, b.y, b.w, b.h);
            ImageIO.write(img.getSubimage(b.x, b.y, b.w, b.h), "png",
                    new File(outdir + File.separator + String.format("comp_%03d.png", i)));
            g2.drawRect(b.x, b.y, b.w, b.h);
            g2.setColor(new Color(255, 255, 0, 220));
            g2.drawString(String.valueOf(i), b.x + 2, b.y + 24);
            g2.setColor(new Color(255, 0, 0, 160));
            i++;
        }
        pw.close();
        g2.dispose();
        ImageIO.write(contact, "png", new File(outdir + File.separator + "preview.png"));
        System.out.println("sliced " + list.size() + " components -> " + outdir);
    }

    static boolean[] dilate(boolean[] src, int W, int H, int r) {
        boolean[] out = new boolean[W * H];
        for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++) {
                if (!src[y * W + x]) continue;
                for (int dy = -r; dy <= r; dy++) {
                    int ny = y + dy; if (ny < 0 || ny >= H) continue;
                    for (int dx = -r; dx <= r; dx++) {
                        int nx = x + dx; if (nx < 0 || nx >= W) continue;
                        out[ny * W + nx] = true;
                    }
                }
            }
        return out;
    }

    /** clear mask bits that are isolated noise (<=1 opaque neighbour in 3x3) */
    static void despeckle(byte[] mask, int w, int h) {
        for (int pass = 0; pass < 2; pass++) {
            byte[] copy = mask.clone();
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++) {
                    int o = y * w + x;
                    if ((copy[o >> 3] & (0x80 >> (o & 7))) == 0) continue;
                    int nb = 0;
                    for (int dy = -1; dy <= 1 && nb <= 1; dy++)
                        for (int dx = -1; dx <= 1 && nb <= 1; dx++) {
                            if (dx == 0 && dy == 0) continue;
                            int nx = x + dx, ny = y + dy;
                            if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
                            int q = ny * w + nx;
                            if ((copy[q >> 3] & (0x80 >> (q & 7))) != 0) nb++;
                        }
                    if (nb <= 1) mask[o >> 3] &= (byte) ~(0x80 >> (o & 7));
                }
        }
    }

    // ------------------------------------------------------------------ build
    static void doBuild(String manifestPath, String outdir) throws Exception {
        new File(outdir).mkdirs();
        Map<String, BufferedImage> sheets = new HashMap<>();
        java.util.List<String> defines = new ArrayList<>();
        BufferedReader br = new BufferedReader(new FileReader(manifestPath));
        String line;
        while ((line = br.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] t = line.split("\\s+");
            // name sheet x y w h outW outH [opaque]
            String name = t[0];
            BufferedImage sheet = sheets.computeIfAbsent(t[1], p -> {
                try { return ImageIO.read(new File(p)); }
                catch (Exception e) { throw new RuntimeException(e); }
            });
            int x = Integer.parseInt(t[2]), y = Integer.parseInt(t[3]);
            int w = Integer.parseInt(t[4]), h = Integer.parseInt(t[5]);
            int ow = Integer.parseInt(t[6]), oh = Integer.parseInt(t[7]);
            boolean forceOpaque = t.length > 8 && t[8].equals("opaque");
            BufferedImage crop = sheet.getSubimage(x, y, w, h);
            short[] px = new short[ow * oh];
            byte[] mask = forceOpaque ? new byte[0] : new byte[(ow * oh + 7) / 8];
            for (int oy = 0; oy < oh; oy++) {
                // box-filter source window for downscale, exact pixel for upscale
                int sy0 = oy * h / oh, sy1 = Math.max(sy0 + 1, (oy + 1) * h / oh);
                for (int ox = 0; ox < ow; ox++) {
                    int sx0 = ox * w / ow, sx1 = Math.max(sx0 + 1, (ox + 1) * w / ow);
                    long sr = 0, sg = 0, sb = 0, n = 0;
                    boolean anyOpaque = false, allOpaque = true;
                    for (int sy = sy0; sy < sy1 && sy < h; sy++) {
                        for (int sx = sx0; sx < sx1 && sx < w; sx++) {
                            int argb = crop.getRGB(sx, sy);
                            int a = (argb >>> 24) & 0xFF;
                            int r = (argb >> 16) & 0xFF, g = (argb >> 8) & 0xFF, b = argb & 0xFF;
                            boolean solid;
                            int mn = Math.min(r, Math.min(g, b)), mx = Math.max(r, Math.max(g, b));
                            if (a == 255) solid = !(mn >= 232 && (mx - mn) <= 20); // noisy near-white bg
                            else solid = a >= 128;
                            if (solid) { anyOpaque = true; sr += r; sg += g; sb += b; n++; }
                            else allOpaque = false;
                        }
                    }
                    int o = oy * ow + ox;
                    if (anyOpaque) {
                        // average solid pixels only so white bg never bleeds into edges
                        int r = (int) (sr / n), g = (int) (sg / n), b = (int) (sb / n);
                        if (r > 248 && g < 8 && b > 248) { r = 240; b = 240; } // keep clear of any key use
                        px[o] = (short) (((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
                        if (!forceOpaque && allOpaque) mask[o >> 3] |= (byte) (0x80 >> (o & 7));
                    }
                }
            }
            if (!forceOpaque) despeckle(mask, ow, oh);
            try (DataOutputStream out = new DataOutputStream(new BufferedOutputStream(
                    new FileOutputStream(outdir + File.separator + name + ".raw")))) {
                // 8-byte header: w le16, h le16, flags le16 (1=opaque), reserved le16
                out.writeByte(ow & 0xFF); out.writeByte((ow >> 8) & 0xFF);
                out.writeByte(oh & 0xFF); out.writeByte((oh >> 8) & 0xFF);
                out.writeByte(forceOpaque ? 1 : 0); out.writeByte(0);
                out.writeByte(0); out.writeByte(0);
                for (short p : px) { out.writeByte(p & 0xFF); out.writeByte((p >> 8) & 0xFF); }
                out.write(mask);
            }
            int total = 8 + ow * oh * 2 + mask.length;
            defines.add(String.format("%s: %dx%d flags=%d %d bytes", name, ow, oh, forceOpaque ? 1 : 0, total));
            System.out.printf(Locale.ROOT, "%-16s %4dx%-4d -> %d bytes%n", name, ow, oh, total);
        }
        br.close();
        try (PrintWriter pw = new PrintWriter(new FileWriter(outdir + File.separator + "sprites.txt"))) {
            pw.println("/* generated by AssetTool - do not edit */");
            for (String d : defines) pw.println(d);
        }
    }
}
