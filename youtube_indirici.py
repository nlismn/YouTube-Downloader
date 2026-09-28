import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
# AYARLAR
# ============================================================

DOWNLOAD_DIR = (
    Path.home()
    / "storage"
    / "shared"
    / "Download"
    / "YouTube"
)

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".m4a",
    ".mov",
    ".avi",
    ".flv",
    ".ts",
}

RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
GRAY = "\033[90m"
BLUE = "\033[94m"
BOLD = "\033[1m"


# ============================================================
# EKRAN / YARDIMCI
# ============================================================

def clear():
    print("\033[2J\033[H", end="")


def pause():
    input(f"\n{GRAY}Devam etmek için ENTER...{RESET}")


def format_size(size):
    if size is None or size <= 0:
        return "Bilinmiyor"

    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size)

    for unit in units:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} PiB"


def format_duration(seconds):
    if not seconds:
        return "Bilinmiyor"

    try:
        seconds = int(seconds)
    except Exception:
        return "Bilinmiyor"

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"

    return f"{m:02d}:{s:02d}"


def get_size(fmt):
    size = fmt.get("filesize")

    if size is None:
        size = fmt.get("filesize_approx")

    return size or 0


def run_command(command):
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None


# ============================================================
# PROGRAM KONTROLÜ
# ============================================================

def check_programs():
    required = [
        "python",
        "yt-dlp",
        "ffmpeg",
        "deno",
    ]

    missing = []

    for program in required:
        if shutil.which(program) is None:
            missing.append(program)

    if missing:
        print(f"{RED}Eksik program(lar):{RESET}")

        for program in missing:
            print(f"  - {program}")

        print()
        print(
            "Gerekli programları Termux'ta kurmak için:"
        )
        print()
        print(
            "pkg install python ffmpeg yt-dlp deno"
        )

        sys.exit(1)


# ============================================================
# VİDEO BİLGİSİ
# ============================================================

def get_video_info(url):
    command = [
        "yt-dlp",
        "--js-runtimes",
        "deno",
        "--skip-download",
        "--no-warnings",
        "-J",
        url,
    ]

    result = run_command(command)

    if result is None:
        return None

    if result.returncode != 0:
        print()
        print(
            f"{RED}Video bilgileri alınamadı.{RESET}"
        )

        if result.stderr:
            print(result.stderr.strip())

        return None

    try:
        return json.loads(result.stdout)

    except json.JSONDecodeError:
        print(
            f"{RED}yt-dlp çıktısı okunamadı.{RESET}"
        )
        return None


# ============================================================
# FORMATLARI AYIR
# ============================================================

def get_formats(info):
    formats = info.get("formats", [])

    video_formats = []
    audio_formats = []

    for fmt in formats:
        height = fmt.get("height")
        vcodec = fmt.get("vcodec")
        acodec = fmt.get("acodec")
        ext = fmt.get("ext")

        if (
            height
            and vcodec
            and vcodec != "none"
            and (
                not acodec
                or acodec == "none"
            )
            and ext == "mp4"
        ):
            video_formats.append(fmt)

        if (
            acodec
            and acodec != "none"
            and (
                not vcodec
                or vcodec == "none"
            )
        ):
            audio_formats.append(fmt)

    return video_formats, audio_formats


# ============================================================
# EN İYİ SES
# ============================================================

def find_best_audio(audio_formats):
    if not audio_formats:
        return None

    m4a_formats = [
        fmt
        for fmt in audio_formats
        if fmt.get("ext") == "m4a"
    ]

    candidates = (
        m4a_formats
        if m4a_formats
        else audio_formats
    )

    def score(fmt):
        abr = fmt.get("abr") or 0
        size = get_size(fmt)

        return (
            float(abr),
            size,
        )

    return max(
        candidates,
        key=score,
    )


# ============================================================
# VİDEO KALİTE SEÇİMLERİ
# ============================================================

def find_1080(video_formats):
    candidates = [
        f
        for f in video_formats
        if f.get("height") == 1080
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda f: (
            f.get("fps") or 0,
            get_size(f),
        ),
    )


def find_720_60(video_formats):
    candidates = [
        f
        for f in video_formats
        if f.get("height") == 720
        and (f.get("fps") or 0) >= 60
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda f: (
            f.get("fps") or 0,
            get_size(f),
        ),
    )


def find_720(video_formats):
    candidates = [
        f
        for f in video_formats
        if f.get("height") == 720
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda f: (
            f.get("fps") or 0,
            get_size(f),
        ),
    )


def find_smallest(video_formats):
    if not video_formats:
        return None

    return min(
        video_formats,
        key=lambda f: (
            f.get("height") or 999999,
            get_size(f),
        ),
    )
# ============================================================
# KALİTE ADI
# ============================================================

def quality_label(fmt):
    if not fmt:
        return "Bilinmiyor"

    height = fmt.get("height") or 0
    fps = fmt.get("fps") or 0

    if height >= 2160:
        label = "2160p"
    elif height >= 1440:
        label = "1440p"
    elif height >= 1080:
        label = "1080p"
    elif height >= 720:
        label = "720p"
    elif height >= 480:
        label = "480p"
    elif height >= 360:
        label = "360p"
    elif height >= 240:
        label = "240p"
    else:
        label = f"{height}p"

    if fps >= 60:
        label += "60"

    return label


# ============================================================
# SES AÇIKLAMASI
# ============================================================

def audio_description(audio):
    if not audio:
        return "Ses bulunamadı"

    abr = audio.get("abr")
    acodec = audio.get("acodec") or "Bilinmiyor"

    if abr:
        return f"{abr:.0f} kbps / {acodec}"

    return acodec


# ============================================================
# TOPLAM BOYUT
# ============================================================

def estimated_total_size(video, audio):
    return (
        get_size(video)
        + get_size(audio)
    )


# ============================================================
# SEÇENEK GÖSTER
# ============================================================

def show_option(
    number,
    label,
    video,
    audio,
):
    if not video:
        print(
            f"{GRAY}"
            f"{number}) {label}: "
            f"Bu kalite mevcut değil."
            f"{RESET}"
        )
        return

    video_size = get_size(video)
    audio_size = get_size(audio)

    total = (
        video_size
        + audio_size
    )

    height = video.get("height") or 0
    fps = video.get("fps") or 0
    vcodec = video.get("vcodec") or "Bilinmiyor"

    actual_quality = (
        f"{height}p"
        f"{'60' if fps >= 60 else ''}"
    )

    print(
        f"{GREEN}{number}) {label}{RESET}"
        f" [{actual_quality}]"
    )

    print(
        f"   Video : {vcodec}"
    )

    print(
        f"   Ses   : "
        f"{audio_description(audio)}"
    )

    print(
        f"   Tahmini boyut: "
        f"{format_size(total)}"
    )


# ============================================================
# VİDEO SEÇ
# ============================================================

def get_video_selection(index):
    while True:
        print()
        print(
            f"{CYAN}{BOLD}"
            f"========== VİDEO {index} =========="
            f"{RESET}"
        )

        url = input(
            "YouTube URL: "
        ).strip()

        if not url:
            print(
                f"{RED}"
                "URL boş bırakılamaz."
                f"{RESET}"
            )
            continue

        print()
        print(
            f"{YELLOW}"
            "Video bilgileri Deno + yt-dlp "
            "ile alınıyor..."
            f"{RESET}"
        )

        info = get_video_info(url)

        if not info:
            print()
            print(
                f"{RED}"
                "Video bilgileri alınamadı."
                f"{RESET}"
            )

            retry = input(
                "Tekrar denemek ister misin? "
                "(E/h): "
            ).strip().lower()

            if retry in (
                "h",
                "hayır",
                "hayir",
                "n",
            ):
                return None

            continue

        title = (
            info.get("title")
            or "Bilinmeyen video"
        )

        duration = format_duration(
            info.get("duration")
        )

        video_formats, audio_formats = (
            get_formats(info)
        )

        best_audio = find_best_audio(
            audio_formats
        )

        if not video_formats:
            print(
                f"{RED}"
                "Uygun MP4 video formatı "
                "bulunamadı."
                f"{RESET}"
            )
            return None

        print()
        print(
            f"{BOLD}{WHITE}"
            f"Başlık: {title}"
            f"{RESET}"
        )

        print(
            f"{BOLD}{WHITE}"
            f"Süre  : {duration}"
            f"{RESET}"
        )

        print(
            f"{BOLD}{WHITE}"
            f"Ses   : "
            f"{audio_description(best_audio)}"
            f"{RESET}"
        )

        option_1080 = find_1080(
            video_formats
        )

        option_720_60 = find_720_60(
            video_formats
        )

        option_720 = find_720(
            video_formats
        )

        option_smallest = find_smallest(
            video_formats
        )

        print()
        print(
            f"{CYAN}{BOLD}"
            "========= KALİTE SEÇENEKLERİ ========="
            f"{RESET}"
        )
        print()

        show_option(
            1,
            "1080p",
            option_1080,
            best_audio,
        )

        show_option(
            2,
            "720p60",
            option_720_60,
            best_audio,
        )

        show_option(
            3,
            "720p",
            option_720,
            best_audio,
        )

        show_option(
            4,
            "En küçük uygun kalite",
            option_smallest,
            best_audio,
        )

        while True:
            choice = input(
                "\nKalite seç (1-4): "
            ).strip()

            selected = None

            if choice == "1":
                selected = option_1080

            elif choice == "2":
                selected = option_720_60

            elif choice == "3":
                selected = option_720

            elif choice == "4":
                selected = option_smallest

            else:
                print(
                    f"{RED}"
                    "1, 2, 3 veya 4 gir."
                    f"{RESET}"
                )
                continue

            if not selected:
                print(
                    f"{RED}"
                    "Bu kalite bu videoda "
                    "mevcut değil."
                    f"{RESET}"
                )
                continue

            total = estimated_total_size(
                selected,
                best_audio,
            )

            return {
                "url": url,
                "title": title,
                "video": selected,
                "audio": best_audio,
                "quality": quality_label(
                    selected
                ),
                "size": total,
            }


# ============================================================
# ÖZET
# ============================================================

def show_summary(videos):
    print()
    print(
        f"{CYAN}{BOLD}"
        "=============== İNDİRME ÖZETİ ==============="
        f"{RESET}"
    )

    total_size = 0

    for index, item in enumerate(
        videos,
        1,
    ):
        print()
        print(
            f"{WHITE}{index}. "
            f"{item['title']}"
            f"{RESET}"
        )

        print(
            f"   Kalite : "
            f"{GREEN}"
            f"{item['quality']}"
            f"{RESET}"
        )

        print(
            f"   Boyut  : "
            f"{format_size(item['size'])}"
        )

        total_size += item["size"]

    print()
    print(
        f"{BOLD}{YELLOW}"
        f"TOPLAM TAHMİNİ BOYUT: "
        f"{format_size(total_size)}"
        f"{RESET}"
    )

    return total_size


# ============================================================
# İPTAL
# ============================================================

def cancel_videos(videos):
    print()
    print(
        f"{CYAN}{BOLD}"
        "İPTAL EDİLECEK VİDEOLAR"
        f"{RESET}"
    )

    print(
        "ENTER = hiçbirini iptal etme"
    )

    print(
        "Örnek: 2"
    )

    print(
        "Birden fazla: 2,4"
    )

    while True:
        answer = input(
            "\nİptal: "
        ).strip()

        if not answer:
            return videos

        try:
            numbers = [
                int(x.strip())
                for x in answer.split(",")
                if x.strip()
            ]
        except ValueError:
            print(
                f"{RED}"
                "Geçersiz giriş."
                f"{RESET}"
            )
            continue

        if any(
            n < 1 or n > len(videos)
            for n in numbers
        ):
            print(
                f"{RED}"
                "Video numarası geçersiz."
                f"{RESET}"
            )
            continue

        numbers = set(numbers)

        return [
            item
            for index, item in enumerate(
                videos,
                1,
            )
            if index not in numbers
        ]
# ============================================================
# İLERLEME ÇUBUKLARI
# ============================================================

def progress_bar(
    percent,
    width=30,
):
    percent = max(
        0.0,
        min(100.0, percent),
    )

    filled = int(
        width * percent / 100
    )

    empty = width - filled

    return (
        "["
        + "#" * filled
        + "-" * empty
        + "]"
    )


def show_progress(
    current_percent,
    completed_count,
    total_count,
):
    overall_percent = (
        (
            completed_count
            + current_percent / 100
        )
        / total_count
    ) * 100

    current_bar = progress_bar(
        current_percent
    )

    overall_bar = progress_bar(
        overall_percent
    )

    print(
        f"\r"
        f"Video:   "
        f"{current_bar} "
        f"{current_percent:6.2f}%"
        f"   |   "
        f"Genel:   "
        f"{overall_bar} "
        f"{overall_percent:6.2f}%",
        end="",
        flush=True,
    )


def extract_percent(line):
    matches = re.findall(
        r"(\d+(?:\.\d+)?)%",
        line,
    )

    if not matches:
        return None

    try:
        return float(matches[-1])
    except ValueError:
        return None


# ============================================================
# VİDEO İNDİR
# ============================================================

def download_video(
    item,
    index,
    total_count,
):
    video = item["video"]
    audio = item["audio"]

    video_id = video.get(
        "format_id"
    )

    audio_id = (
        audio.get("format_id")
        if audio
        else None
    )

    if not video_id:
        print(
            f"{RED}"
            "Video format ID bulunamadı."
            f"{RESET}"
        )
        return False

    if audio_id:
        format_string = (
            f"{video_id}+{audio_id}"
        )
    else:
        format_string = video_id

    print()
    print(
        f"{CYAN}{BOLD}"
        f"========== {index}/{total_count} =========="
        f"{RESET}"
    )

    print(
        f"{WHITE}"
        f"{item['title']}"
        f"{RESET}"
    )

    print(
        f"Kalite: "
        f"{GREEN}"
        f"{item['quality']}"
        f"{RESET}"
    )

    print(
        f"Tahmini boyut: "
        f"{format_size(item['size'])}"
    )

    print()
    print(
        f"{YELLOW}"
        "Deno + yt-dlp ile indirme..."
        f"{RESET}"
    )

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "yt-dlp",

        # DENO
        "--js-runtimes",
        "deno",

        # Video + ses
        "-f",
        format_string,

        # MP4 olarak birleştir
        "--merge-output-format",
        "mp4",

        # İlerleme bilgisini satır satır ver
        "--newline",

        # Dosya adı
        "-o",
        str(
            DOWNLOAD_DIR
            / "%(title)s.%(ext)s"
        ),

        # URL
        item["url"],
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    except Exception as error:
        print()
        print(
            f"{RED}"
            f"İndirme başlatılamadı: {error}"
            f"{RESET}"
        )
        return False

    last_percent = 0.0

    try:
        for line in process.stdout:
            line = line.rstrip()

            percent = extract_percent(
                line
            )

            if percent is not None:
                last_percent = percent

                show_progress(
                    last_percent,
                    index - 1,
                    total_count,
                )

        process.wait()

    except KeyboardInterrupt:
        print()
        print(
            f"{YELLOW}"
            "İndirme kullanıcı tarafından "
            "durduruldu."
            f"{RESET}"
        )

        process.terminate()

        try:
            process.wait(
                timeout=3
            )
        except subprocess.TimeoutExpired:
            process.kill()

        return False

    print()

    if process.returncode == 0:

        show_progress(
            100.0,
            index - 1,
            total_count,
        )

        print()

        print(
            f"{GREEN}{BOLD}"
            "✓ İndirme tamamlandı."
            f"{RESET}"
        )

        return True

    print()

    print(
        f"{RED}{BOLD}"
        "✗ İndirme başarısız."
        f"{RESET}"
    )

    return False


# ============================================================
# GÜVENLİ DOSYA LİSTELEME
# ============================================================

def get_downloaded_files():
    if not DOWNLOAD_DIR.exists():
        return []

    files = []

    try:
        for path in DOWNLOAD_DIR.iterdir():

            # Sadece normal dosyalar
            if not path.is_file():
                continue

            # Sadece video dosyaları
            if (
                path.suffix.lower()
                not in VIDEO_EXTENSIONS
            ):
                continue

            files.append(path)

    except OSError:
        return []

    return sorted(
        files,
        key=lambda p: p.name.lower(),
    )


# ============================================================
# GÜVENLİ DOSYA SİLME MENÜSÜ
# ============================================================

def delete_menu():
    while True:
        clear()

        print(
            f"{CYAN}{BOLD}"
            "============== DOSYA YÖNETİMİ =============="
            f"{RESET}"
        )

        print()
        print(
            f"Klasör:\n"
            f"{DOWNLOAD_DIR}"
        )

        files = get_downloaded_files()

        print()

        if not files:
            print(
                f"{YELLOW}"
                "Bu klasörde indirilebilir video "
                "dosyası bulunamadı."
                f"{RESET}"
            )

            pause()
            return

        for index, path in enumerate(
            files,
            1,
        ):
            try:
                size = path.stat().st_size
            except OSError:
                size = 0

            print(
                f"{index}) "
                f"{path.name}"
                f"  "
                f"({format_size(size)})"
            )

        print()
        print(
            "1 = Tek video sil"
        )

        print(
            "2 = Listedeki tüm videoları sil"
        )

        print(
            "0 = Geri dön"
        )

        choice = input(
            "\nSeçim: "
        ).strip()

        # ====================================================
        # GERİ
        # ====================================================

        if choice == "0":
            return

        # ====================================================
        # TEK DOSYA
        # ====================================================

        if choice == "1":

            while True:
                number = input(
                    "\nSilinecek video numarası "
                    "(0 = geri): "
                ).strip()

                if number == "0":
                    break

                try:
                    index = int(number)

                except ValueError:
                    print(
                        f"{RED}"
                        "Geçersiz numara."
                        f"{RESET}"
                    )
                    continue

                if (
                    index < 1
                    or index > len(files)
                ):
                    print(
                        f"{RED}"
                        "Böyle bir video yok."
                        f"{RESET}"
                    )
                    continue

                target = files[index - 1]

                print()
                print(
                    f"{YELLOW}"
                    "SİLİNECEK DOSYA:"
                    f"{RESET}"
                )

                print(
                    target.name
                )

                confirm = input(
                    "\nSilmek için "
                    "SIL yaz: "
                )

                if confirm != "SIL":
                    print(
                        f"{GREEN}"
                        "Silme iptal edildi."
                        f"{RESET}"
                    )

                    pause()
                    break

                # ------------------------------------------------
                # GÜVENLİK KONTROLÜ
                # ------------------------------------------------

                try:
                    target.resolve().relative_to(
                        DOWNLOAD_DIR.resolve()
                    )

                except ValueError:
                    print(
                        f"{RED}"
                        "Güvenlik kontrolü başarısız. "
                        "Dosya silinmedi."
                        f"{RESET}"
                    )

                    pause()
                    break

                try:
                    target.unlink()

                    print(
                        f"{GREEN}"
                        "✓ Dosya silindi."
                        f"{RESET}"
                    )

                except OSError as error:
                    print(
                        f"{RED}"
                        f"Dosya silinemedi: {error}"
                        f"{RESET}"
                    )

                pause()
                break

        # ====================================================
        # TÜM VİDEOLAR
        # ====================================================

        elif choice == "2":

            print()
            print(
                f"{RED}{BOLD}"
                "DİKKAT"
                f"{RESET}"
            )

            print(
                "Silinecek klasör:"
            )

            print(
                DOWNLOAD_DIR
            )

            print()

            print(
                f"{YELLOW}"
                f"Silinecek video sayısı: "
                f"{len(files)}"
                f"{RESET}"
            )

            print()

            confirm = input(
                "HEPSİNİ silmek için "
                "tam olarak SIL yaz: "
            )

            if confirm != "SIL":
                print()
                print(
                    f"{GREEN}"
                    "Silme işlemi iptal edildi."
                    f"{RESET}"
                )

                pause()
                continue

            deleted = 0
            failed = 0

            for target in files:

                # Her dosyada güvenlik kontrolü
                try:
                    target.resolve().relative_to(
                        DOWNLOAD_DIR.resolve()
                    )

                except ValueError:
                    failed += 1
                    continue

                try:
                    if (
                        target.is_file()
                        and target.suffix.lower()
                        in VIDEO_EXTENSIONS
                    ):
                        target.unlink()
                        deleted += 1

                except OSError:
                    failed += 1

            print()
            print(
                f"{GREEN}"
                f"Silinen dosya: {deleted}"
                f"{RESET}"
            )

            if failed:
                print(
                    f"{RED}"
                    f"Silinemeyen dosya: {failed}"
                    f"{RESET}"
                )

            pause()

        else:
            print(
                f"{RED}"
                "Geçersiz seçim."
                f"{RESET}"
            )

            pause()
# ============================================================
# İNDİRME MODU
# ============================================================

def download_mode():
    clear()

    print(
        f"{CYAN}{BOLD}"
        "============== YOUTUBE İNDİR =============="
        f"{RESET}"
    )

    print()

    # --------------------------------------------------------
    # KAÇ VİDEO?
    # --------------------------------------------------------

    while True:
        count_text = input(
            "Kaç video indirmek istiyorsun? "
        ).strip()

        try:
            count = int(count_text)

            if count >= 1:
                break

            print(
                f"{RED}"
                "En az 1 video girmelisin."
                f"{RESET}"
            )

        except ValueError:
            print(
                f"{RED}"
                "Geçerli bir sayı gir."
                f"{RESET}"
            )

    videos = []

    # --------------------------------------------------------
    # VİDEOLARIN URL'LERİNİ TEK TEK AL
    # --------------------------------------------------------

    for index in range(1, count + 1):

        print()
        print(
            f"{BLUE}{BOLD}"
            "--------------------------------------------"
            f"{RESET}"
        )

        print(
            f"{CYAN}"
            f"Video {index}/{count}"
            f"{RESET}"
        )

        try:
            item = get_video_selection(
                index
            )

        except KeyboardInterrupt:
            print()
            print(
                f"{YELLOW}"
                "İşlem iptal edildi."
                f"{RESET}"
            )

            pause()
            return

        if item is None:
            print(
                f"{RED}"
                "Bu video eklenemedi."
                f"{RESET}"
            )

            pause()
            return

        videos.append(item)

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    clear()

    show_summary(
        videos
    )

    # --------------------------------------------------------
    # İPTAL EDİLECEK VİDEOLAR
    # --------------------------------------------------------

    videos = cancel_videos(
        videos
    )

    if not videos:
        print()
        print(
            f"{YELLOW}"
            "İndirilecek video kalmadı."
            f"{RESET}"
        )

        pause()
        return

    # --------------------------------------------------------
    # İPTALLERDEN SONRA TEKRAR ÖZET
    # --------------------------------------------------------

    clear()

    print(
        f"{CYAN}{BOLD}"
        "============== SON KONTROL =============="
        f"{RESET}"
    )

    print()

    show_summary(
        videos
    )

    print()

    print(
        f"{YELLOW}"
        "İndirmeyi başlatmak için ENTER'a bas."
        f"{RESET}"
    )

    print(
        f"{GRAY}"
        "İptal etmek için H yazabilirsin."
        f"{RESET}"
    )

    start = input(
        "\nSeçim: "
    ).strip().lower()

    if start == "h":
        print(
            f"{YELLOW}"
            "İndirme iptal edildi."
            f"{RESET}"
        )

        pause()
        return

    # --------------------------------------------------------
    # İNDİRMELER
    # --------------------------------------------------------

    clear()

    print(
        f"{CYAN}{BOLD}"
        "============== İNDİRMELER =============="
        f"{RESET}"
    )

    print()

    total_count = len(videos)

    successful = 0
    failed = 0

    for index, item in enumerate(
        videos,
        1,
    ):

        result = download_video(
            item,
            index,
            total_count,
        )

        if result:
            successful += 1
        else:
            failed += 1

        print()

        if index < total_count:
            print(
                f"{GRAY}"
                "Sonraki videoya geçiliyor..."
                f"{RESET}"
            )

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    print()
    print(
        f"{CYAN}{BOLD}"
        "============================================"
        f"{RESET}"
    )

    print(
        f"{GREEN}"
        f"Başarılı: {successful}"
        f"{RESET}"
    )

    print(
        f"{RED}"
        f"Başarısız: {failed}"
        f"{RESET}"
    )

    print()
    print(
        "Dosyaların bulunduğu klasör:"
    )

    print(
        f"{BLUE}"
        f"{DOWNLOAD_DIR}"
        f"{RESET}"
    )

    pause()


# ============================================================
# ANA MENÜ
# ============================================================

def main():
    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    check_programs()

    while True:
        clear()

        print(
            f"{CYAN}{BOLD}"
            "============================================"
            f"{RESET}"
        )

        print(
            f"{CYAN}{BOLD}"
            "          YOUTUBE İNDİRİCİ"
            f"{RESET}"
        )

        print(
            f"{CYAN}{BOLD}"
            "============================================"
            f"{RESET}"
        )

        print()

        print(
            "1) YouTube video indir"
        )

        print(
            "2) İndirilen videoları yönet / sil"
        )

        print(
            "0) Çıkış"
        )

        print()

        choice = input(
            "Seçim: "
        ).strip()

        # ----------------------------------------------------
        # VİDEO İNDİR
        # ----------------------------------------------------

        if choice == "1":

            try:
                download_mode()

            except KeyboardInterrupt:
                print()
                print()
                print(
                    f"{YELLOW}"
                    "İşlem iptal edildi."
                    f"{RESET}"
                )

                pause()

        # ----------------------------------------------------
        # DOSYA YÖNETİMİ
        # ----------------------------------------------------

        elif choice == "2":

            try:
                delete_menu()

            except KeyboardInterrupt:
                print()
                print()
                print(
                    f"{YELLOW}"
                    "Dosya yönetimi iptal edildi."
                    f"{RESET}"
                )

                pause()

        # ----------------------------------------------------
        # ÇIKIŞ
        # ----------------------------------------------------

        elif choice == "0":

            clear()

            print(
                f"{GREEN}"
                "Program kapatıldı."
                f"{RESET}"
            )

            break

        # ----------------------------------------------------
        # GEÇERSİZ
        # ----------------------------------------------------

        else:

            print()

            print(
                f"{RED}"
                "Geçersiz seçim."
                f"{RESET}"
            )

            pause()


# ============================================================
# PROGRAMI BAŞLAT
# ============================================================

if __name__ == "__main__":
    main()
