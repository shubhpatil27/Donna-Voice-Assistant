from PIL import Image
import os

src = "your_icon.png"   # change if needed
out = "donna_icon.ico"
sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]

img = Image.open(src).convert("RGBA")
w,h = img.size
s = max(w,h)
# pad square with transparent background
new = Image.new("RGBA", (s,s), (0,0,0,0))
new.paste(img, ((s-w)//2, (s-h)//2), img)
# resize to a big square first (512)
new = new.resize((512,512), Image.LANCZOS)

# Save ICO with multiple sizes
new.save(out, format="ICO", sizes=sizes)
print("Wrote", out)
