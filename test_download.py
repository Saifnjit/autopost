import subprocess, json, os

print("Step 1: Searching YouTube...")
result = subprocess.run([
    "yt-dlp", "ytsearch1:openai news 2025",
    "--dump-json", "--no-download", "--quiet", "--no-warnings",
], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)

print(f"  Return code: {result.returncode}")
print(f"  Output length: {len(result.stdout)} chars")

if not result.stdout.strip():
    print("  FAILED: No output from search")
    exit()

v = json.loads(result.stdout.strip().split('\n')[0])
url = v['webpage_url']
print(f"  Found: {v.get('title', '')[:60]}")
print(f"  URL: {url}")

print("\nStep 2: Downloading...")
dl = subprocess.run([
    "yt-dlp", url,
    "-o", "test_clip.mp4",
    "--format", "18/best[height<=360][ext=mp4]/best[ext=mp4]",
    "--no-playlist",
], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)

print(f"  Return code: {dl.returncode}")
if dl.stdout: print(f"  stdout: {dl.stdout[-200:]}")
if dl.stderr: print(f"  stderr: {dl.stderr[-400:]}")

if os.path.exists("test_clip.mp4"):
    size = os.path.getsize("test_clip.mp4")
    print(f"\n  SUCCESS: test_clip.mp4 = {size // 1024}KB")
else:
    print("\n  FAILED: File not created")
