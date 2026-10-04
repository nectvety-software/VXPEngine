/* AssetSheet - render docs/asset_sheet_preview.png from resources/gen/*.raw
 * Usage: java AssetSheet <gen_dir> <out_png>
 * Grid of all sprites (x2 zoom, dark checker bg, name labels). Splash excluded.
 */
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.*;

public class AssetSheet {
    static final int HDR = 8, ZOOM = 2, CELL = 108, LABEL = 14, COLS = 8;

    public static void main(String[] args) throws Exception {
        File dir = new File(args[0]);
        File[] files = dir.listFiles((d, n) -> n.endsWith(".raw") && !n.equals("splash.raw"));
        Arrays.sort(files, Comparator.comparing(File::getName));
        int rows = (files.length + COLS - 1) / COLS;
        BufferedImage img = new BufferedImage(COLS * CELL, rows * (CELL + LABEL), TYPE);
        Graphics2D g = img.createGraphics();
        g.setColor(new Color(24, 24, 34)); g.fillRect(0, 0, img.getWidth(), img.getHeight());
        g.setFont(new Font("Monospaced", Font.PLAIN, 11));

        int i = 0;
        for (File f : files) {
            int cx = (i % COLS) * CELL, cy = (i / COLS) * (CELL + LABEL);
            /* checker */
            for (int y = 0; y < CELL; y += 8)
                for (int x = 0; x < CELL; x += 8)
                    if (((x + y) / 8) % 2 == 0) { g.setColor(new Color(34,34,48)); g.fillRect(cx+x, cy+y, 8, 8); }
            int[] px = loadRaw(f);
            int w = px[0], h = px[1];
            int[] pix = Arrays.copyOfRange(px, 2, 2 + w * h);
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++) {
                    int c = pix[y * w + x];
                    if (c < 0) continue; /* transparent bit set */
                    int r = ((c >> 11) & 31) * 255 / 31, gr = ((c >> 5) & 63) * 255 / 63, b = (c & 31) * 255 / 31;
                    g.setColor(new Color(r, gr, b));
                    g.fillRect(cx + 4 + x * ZOOM, cy + 4 + y * ZOOM, ZOOM, ZOOM);
                }
            g.setColor(new Color(220, 220, 160));
            String name = f.getName().replace(".raw", "");
            g.drawString(name, cx + 3, cy + CELL - 3);
            i++;
        }
        g.dispose();
        ImageIO.write(img, "png", new File(args[1]));
        System.out.println("wrote " + args[1] + " (" + files.length + " sprites, " + img.getWidth() + "x" + img.getHeight() + ")");
    }

    static int TYPE = BufferedImage.TYPE_INT_RGB;

    /* returns {w, h, pix...}; transparent pixels marked -1 */
    static int[] loadRaw(File f) throws IOException {
        DataInputStream in = new DataInputStream(new BufferedInputStream(new FileInputStream(f)));
        byte[] all = new byte[(int) f.length()];
        in.readFully(all); in.close();
        int w = (all[0] & 255) | (all[1] << 8);
        int h = (all[2] & 255) | (all[3] << 8);
        int opaque = (all[4] & 255) | (all[5] << 8);
        int[] out = new int[2 + w * h];
        out[0] = w; out[1] = h;
        int off = HDR + w * h * 2;
        for (int p = 0; p < w * h; p++) {
            int c = (all[HDR + p * 2] & 255) | (all[HDR + p * 2 + 1] << 8);
            if (opaque == 0) {
                int bit = (all[off + p / 8] >> (7 - (p & 7))) & 1;
                if (bit == 0) { out[2 + p] = -1; continue; }
            }
            out[2 + p] = c;
        }
        return out;
    }
}
