import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont


DEFAULT_RANGES = [
    (0x20, 0x7F),
    (0x4E00, 0x9FA5),
    (0xFF01, 0xFF60),
]

DEFAULT_NAME_PREFIX = "heiti"


class FontBinMaker:
    def __init__(self, root):
        self.root = root
        self.root.title("FontBinMaker")
        self.root.geometry("720x540")

        self.font_path = tk.StringVar()
        self.name_prefix = tk.StringVar(value=DEFAULT_NAME_PREFIX)
        self.font_size = tk.IntVar(value=16)
        self.bpp = tk.IntVar(value=1)
        self.out_dir = tk.StringVar(value=os.getcwd())

        ttk.Label(root, text="Font File").pack(anchor="w", padx=10, pady=5)

        font_frame = ttk.Frame(root)
        font_frame.pack(fill="x", padx=10)
        ttk.Entry(font_frame, textvariable=self.font_path).pack(side="left", fill="x", expand=True)
        ttk.Button(font_frame, text="Browse", command=self.select_font).pack(side="left", padx=5)

        cfg = ttk.Frame(root)
        cfg.pack(fill="x", padx=10, pady=10)

        ttk.Label(cfg, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.name_prefix, width=16).grid(row=0, column=1, padx=5, sticky="ew")

        ttk.Label(cfg, text="Font Size").grid(row=0, column=2, padx=(20, 0), sticky="w")
        ttk.Spinbox(cfg, from_=8, to=64, textvariable=self.font_size, width=8).grid(row=0, column=3, padx=5)

        ttk.Label(cfg, text="BPP").grid(row=0, column=4, padx=20, sticky="w")
        for i, value in enumerate([1, 2, 4, 8]):
            ttk.Radiobutton(cfg, text=f"{value}bit", variable=self.bpp, value=value).grid(row=0, column=5 + i, padx=3)
        cfg.columnconfigure(1, weight=1)

        ttk.Label(root, text="Unicode Ranges (one per line, e.g. 0x20-0x7F)").pack(anchor="w", padx=10)
        self.range_text = tk.Text(root, height=10)
        self.range_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.range_text.insert("1.0", self.default_ranges_text())

        out_frame = ttk.Frame(root)
        out_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(out_frame, text="Output Dir").pack(side="left")
        ttk.Entry(out_frame, textvariable=self.out_dir).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(out_frame, text="Select", command=self.select_output_dir).pack(side="left")

        self.out_name_label = ttk.Label(root, justify="left")
        self.out_name_label.pack(anchor="w", padx=10, pady=5)
        for variable in (self.name_prefix, self.font_size, self.bpp):
            variable.trace_add("write", self.update_output_name)
        self.update_output_name()

        tip = (
            "Output file name format: text_bpp_size.bin\n"
            "16x16 + 1bit => 32 bytes per glyph\n"
            "Default ranges => 21094 glyphs, expected file size 675008 bytes"
        )
        ttk.Label(root, text=tip, justify="left").pack(anchor="w", padx=10, pady=5)

        ttk.Button(root, text="Generate BIN", command=self.generate).pack(pady=10)

    @staticmethod
    def default_ranges_text():
        return "\n".join(f"0x{start:04X}-0x{end:04X}" for start, end in DEFAULT_RANGES)

    def select_font(self):
        path = filedialog.askopenfilename(filetypes=[("Font", "*.ttf *.ttc *.otf")])
        if path:
            self.font_path.set(path)

    def select_output_dir(self):
        path = filedialog.askdirectory(initialdir=self.out_dir.get() or os.getcwd())
        if path:
            self.out_dir.set(path)

    @staticmethod
    def sanitize_name(text):
        invalid_chars = '<>:"/\\|?*'
        cleaned = "".join("_" if char in invalid_chars else char for char in text.strip())
        return cleaned.strip(" .")

    def build_output_name(self):
        prefix = self.sanitize_name(self.name_prefix.get())
        if not prefix:
            raise ValueError("Name cannot be empty")
        return f"{prefix}_{self.bpp.get()}_{self.font_size.get()}.bin"

    def update_output_name(self, *_args):
        try:
            file_name = self.build_output_name()
        except ValueError:
            file_name = "(please enter a valid name)"
        self.out_name_label.config(text=f"Output File: {file_name}")

    def parse_ranges(self):
        ranges = []
        for raw in self.range_text.get("1.0", "end").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "-" not in line:
                raise ValueError(f"Bad range format: {line}")

            start_text, end_text = line.split("-", 1)
            start = int(start_text.strip(), 16)
            end = int(end_text.strip(), 16)

            if start > end:
                raise ValueError(f"Bad range order: {line}")

            ranges.append((start, end))

        if not ranges:
            raise ValueError("Range list is empty")

        return ranges

    @staticmethod
    def bytes_per_glyph(size, bpp):
        if bpp == 1:
            return (size * size) // 8
        if bpp == 2:
            return (size * size) // 4
        if bpp == 4:
            return (size * size) // 2
        return size * size

    @staticmethod
    def pack_pixels(px, bpp):
        out = bytearray()

        if bpp == 1:
            for i in range(0, len(px), 8):
                value = 0
                for j in range(8):
                    if i + j < len(px) and px[i + j] > 127:
                        value |= (0x80 >> j)
                out.append(value)
            return out

        if bpp == 2:
            for i in range(0, len(px), 4):
                value = 0
                for j in range(4):
                    pixel = (px[i + j] >> 6) if i + j < len(px) else 0
                    value |= (pixel << ((3 - j) * 2))
                out.append(value)
            return out

        if bpp == 4:
            for i in range(0, len(px), 2):
                p1 = (px[i] >> 4) if i < len(px) else 0
                p2 = (px[i + 1] >> 4) if i + 1 < len(px) else 0
                out.append((p1 << 4) | p2)
            return out

        out.extend(px)
        return out

    def glyph_bytes(self, ch, font, size, bpp):
        image = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(image)

        bbox = draw.textbbox((0, 0), ch, font=font)
        if bbox is None:
            bbox = (0, 0, size, size)

        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        x = (size - width) // 2 - bbox[0]
        y = (size - height) // 2 - bbox[1]

        draw.text((x, y), ch, font=font, fill=255)
        return self.pack_pixels(list(image.getdata()), bpp)

    @staticmethod
    def count_codepoints(ranges):
        total = 0
        for start, end in ranges:
            total += (end - start + 1)
        return total

    def validate_config(self):
        size = self.font_size.get()
        bpp = self.bpp.get()
        name_prefix = self.sanitize_name(self.name_prefix.get())

        if not self.font_path.get():
            raise ValueError("Please select a font file first")

        if not os.path.isfile(self.font_path.get()):
            raise ValueError("Font file does not exist")

        if size <= 0:
            raise ValueError("Font size must be > 0")

        if bpp not in (1, 2, 4, 8):
            raise ValueError("BPP must be 1, 2, 4, or 8")

        if not name_prefix:
            raise ValueError("Please enter a valid output name")

        if not self.out_dir.get():
            raise ValueError("Please select an output directory")

        if not os.path.isdir(self.out_dir.get()):
            raise ValueError("Output directory does not exist")

    def generate(self):
        try:
            ranges = self.parse_ranges()
            self.validate_config()
            font = ImageFont.truetype(self.font_path.get(), self.font_size.get())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        out_file = os.path.join(self.out_dir.get(), self.build_output_name())
        total = self.count_codepoints(ranges)
        glyph_size = self.bytes_per_glyph(self.font_size.get(), self.bpp.get())
        expected_size = total * glyph_size

        try:
            with open(out_file, "wb") as file_obj:
                for start, end in ranges:
                    for codepoint in range(start, end + 1):
                        file_obj.write(
                            self.glyph_bytes(
                                chr(codepoint),
                                font,
                                self.font_size.get(),
                                self.bpp.get(),
                            )
                        )
                actual_size = file_obj.tell()
        except Exception as exc:
            messagebox.showerror("Error", f"Generate failed:\n{exc}")
            return

        summary = [
            f"Output: {out_file}",
            f"Glyphs: {total}",
            f"Bytes/Glyph: {glyph_size}",
            f"Actual Size: {actual_size}",
            f"Expected Size: {expected_size}",
        ]

        if actual_size != expected_size:
            summary.append("Warning: actual size does not match expected size")
        else:
            summary.append("OK: size check passed")

        messagebox.showinfo("Done", "\n".join(summary))


if __name__ == "__main__":
    root = tk.Tk()
    FontBinMaker(root)
    root.mainloop()
