"""Interface desktop para comprimir vídeos até um tamanho aproximado."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


class CompressorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Compressor de Vídeo")
        self.geometry("720x510")
        self.minsize(650, 470)

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.target_mb = tk.StringVar(value="400")
        self.audio_kbps = tk.StringVar(value="128")
        self.resolution = tk.StringVar(value="Automática (recomendado)")
        self.preset = tk.StringVar(value="Rápida (recomendado)")
        self.status = tk.StringVar(value="Selecione um vídeo para começar.")
        self.details = tk.StringVar(value="")
        self.progress_info = tk.StringVar(value="")

        self.duration = 0.0
        self.video_height: int | None = None
        self.has_audio = True
        self.process: subprocess.Popen[str] | None = None
        self.cancel_requested = False
        self.started_at = 0.0
        self.encoding_speed = ""
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="Compressor de Vídeo", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 18)
        )

        ttk.Label(root, text="Vídeo de entrada").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.input_path).grid(row=1, column=1, sticky="ew", padx=10)
        ttk.Button(root, text="Procurar...", command=self._choose_input).grid(row=1, column=2)

        ttk.Label(root, text="Salvar como").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(root, textvariable=self.output_path).grid(row=2, column=1, sticky="ew", padx=10)
        ttk.Button(root, text="Escolher...", command=self._choose_output).grid(row=2, column=2)

        options = ttk.LabelFrame(root, text="Configurações", padding=14)
        options.grid(row=3, column=0, columnspan=3, sticky="ew", pady=18)
        for column in range(4):
            options.columnconfigure(column, weight=1)

        ttk.Label(options, text="Tamanho máximo (MB)").grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="Áudio (kbps)").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(options, text="Resolução máxima").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Label(options, text="Velocidade").grid(row=0, column=3, sticky="w", padx=(12, 0))

        ttk.Entry(options, textvariable=self.target_mb, width=14).grid(row=1, column=0, sticky="ew", pady=(5, 0))
        ttk.Combobox(options, textvariable=self.audio_kbps, values=("64", "96", "128", "160", "192"), state="readonly", width=10).grid(
            row=1, column=1, sticky="ew", padx=(12, 0), pady=(5, 0)
        )
        ttk.Combobox(options, textvariable=self.resolution, values=("Automática (recomendado)", "Manter original", "2160p (4K)", "1080p", "720p", "480p"), state="readonly").grid(
            row=1, column=2, sticky="ew", padx=(12, 0), pady=(5, 0)
        )
        ttk.Combobox(options, textvariable=self.preset, values=("Rápida (recomendado)", "Equilibrada", "Melhor qualidade"), state="readonly", width=10).grid(
            row=1, column=3, sticky="ew", padx=(12, 0), pady=(5, 0)
        )

        ttk.Label(root, textvariable=self.details, foreground="#555555").grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(root, textvariable=self.progress_info, font=("Segoe UI", 10, "bold")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(14, 3)
        )
        self.progress = ttk.Progressbar(root, maximum=100, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(2, 8))
        ttk.Label(root, textvariable=self.status, wraplength=650).grid(row=7, column=0, columnspan=3, sticky="w")

        actions = ttk.Frame(root)
        actions.grid(row=8, column=0, columnspan=3, sticky="e", pady=(22, 0))
        self.cancel_button = ttk.Button(actions, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 10))
        self.start_button = ttk.Button(actions, text="Comprimir vídeo", command=self._start)
        self.start_button.pack(side="left")

    def _choose_input(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o vídeo",
            filetypes=(("Vídeos", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"), ("Todos os arquivos", "*.*")),
        )
        if not filename:
            return
        source = Path(filename)
        self.input_path.set(str(source))
        self.output_path.set(str(source.with_name(f"{source.stem}_comprimido.mp4")))
        self.status.set("Analisando o vídeo...")
        threading.Thread(target=self._probe_worker, args=(source,), daemon=True).start()

    def _choose_output(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Salvar vídeo comprimido", defaultextension=".mp4", filetypes=(("Vídeo MP4", "*.mp4"),)
        )
        if filename:
            self.output_path.set(filename)

    def _probe_worker(self, source: Path) -> None:
        try:
            ffprobe = self._find_program("ffprobe")
            command = [ffprobe, "-v", "error", "-show_entries", "format=duration,size", "-show_streams", "-of", "json", str(source)]
            result = subprocess.run(command, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            size = int(data["format"].get("size", source.stat().st_size))
            video = next((s for s in data["streams"] if s.get("codec_type") == "video"), {})
            has_audio = any(s.get("codec_type") == "audio" for s in data["streams"])
            self.events.put(("probed", (duration, size, video.get("width"), video.get("height"), has_audio)))
        except Exception as exc:
            if isinstance(exc, FileNotFoundError):
                self.events.put(("missing_ffmpeg", None))
            else:
                self.events.put(("error", f"Não foi possível analisar o vídeo: {exc}"))

    def _start(self) -> None:
        try:
            source = Path(self.input_path.get())
            output = Path(self.output_path.get())
            target_mb = float(self.target_mb.get().replace(",", "."))
            if not source.is_file():
                raise ValueError("Selecione um vídeo de entrada válido.")
            if source.resolve() == output.resolve():
                raise ValueError("O arquivo de saída deve ser diferente do original.")
            if target_mb <= 1:
                raise ValueError("Informe um tamanho maior que 1 MB.")
            if output.exists() and not messagebox.askyesno("Substituir arquivo?", f"{output.name} já existe. Deseja substituí-lo?"):
                return
            self._find_program("ffmpeg")
            self._find_program("ffprobe")
        except FileNotFoundError:
            self._offer_ffmpeg_install()
            return
        except ValueError as exc:
            messagebox.showerror("Não foi possível iniciar", str(exc))
            return

        self.cancel_requested = False
        self.started_at = time.monotonic()
        self.encoding_speed = ""
        self.progress["value"] = 0
        self.progress_info.set("0%  •  Iniciando...")
        self.start_button["state"] = "disabled"
        self.cancel_button["state"] = "normal"
        self.status.set("Preparando a compressão...")
        presets = {
            "Rápida (recomendado)": "veryfast",
            "Equilibrada": "medium",
            "Melhor qualidade": "slow",
        }
        settings = (
            int(self.audio_kbps.get()),
            presets[self.preset.get()],
            self.resolution.get(),
            self.video_height,
        )
        threading.Thread(
            target=self._compress_worker, args=(source, output, target_mb, settings), daemon=True
        ).start()

    def _compress_worker(
        self, source: Path, output: Path, target_mb: float, settings: tuple[int, str, str, int | None]
    ) -> None:
        partial_output: Path | None = None
        try:
            if self.duration <= 0:
                self._probe_sync(source)
            # Reserva 2% para o contêiner MP4. Duas passagens tornam o tamanho previsível.
            total_kbps = target_mb * 1024 * 1024 * 8 * 0.98 / self.duration / 1000
            selected_audio_kbps, preset, resolution, source_height = settings
            audio_kbps = selected_audio_kbps if self.has_audio else 0
            video_kbps = int(total_kbps - audio_kbps)
            if video_kbps < 100:
                raise ValueError("O limite é pequeno demais para a duração do vídeo. Aumente o tamanho máximo.")

            ffmpeg = self._find_program("ffmpeg")
            scale = self._scale_filter(resolution, source_height)
            common = ["-c:v", "libx264", "-preset", preset, "-b:v", f"{video_kbps}k"]
            if scale:
                common += ["-vf", scale]

            output.parent.mkdir(parents=True, exist_ok=True)
            descriptor, partial_name = tempfile.mkstemp(
                prefix=f".{output.stem}_", suffix=".mp4", dir=output.parent
            )
            os.close(descriptor)
            partial_output = Path(partial_name)
            # No Windows, o FFmpeg pode manter o arquivo .mbtree aberto por alguns
            # instantes após encerrar. Uma falha ao limpar esse log não deve invalidar
            # o vídeo que acabou de ser criado corretamente.
            with tempfile.TemporaryDirectory(
                prefix="compressor_video_", ignore_cleanup_errors=True
            ) as temp_dir:
                passlog = str(Path(temp_dir) / "ffmpeg2pass")
                null_target = "NUL" if os.name == "nt" else "/dev/null"
                first = [ffmpeg, "-v", "error", "-y", "-i", str(source), *common, "-pass", "1",
                         "-passlogfile", passlog, "-an", "-f", "null", "-progress", "pipe:1", "-nostats", null_target]
                self.events.put(("status", f"1ª etapa de 2 — analisando (vídeo: {video_kbps} kbps)..."))
                self._run_ffmpeg(first, 0, 50)

                second = [ffmpeg, "-v", "error", "-y", "-i", str(source), *common, "-pass", "2", "-passlogfile", passlog]
                if self.has_audio:
                    second += ["-c:a", "aac", "-b:a", f"{audio_kbps}k"]
                else:
                    second += ["-an"]
                second += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(partial_output)]
                self.events.put(("status", "2ª etapa de 2 — criando o arquivo final..."))
                self._run_ffmpeg(second, 50, 100)

            if self.cancel_requested:
                self.events.put(("cancelled", None))
            else:
                # O destino só é alterado depois que o MP4 novo está completo.
                os.replace(partial_output, output)
                partial_output = None
                actual_mb = output.stat().st_size / (1024 * 1024)
                self.events.put(("done", (output, actual_mb)))
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            if partial_output and partial_output.exists():
                try:
                    partial_output.unlink()
                except OSError:
                    # O Windows pode liberar o arquivo alguns milissegundos depois.
                    pass

    def _probe_sync(self, source: Path) -> None:
        command = [self._find_program("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-select_streams", "a", "-show_entries", "stream=index", "-of", "json", str(source)]
        result = subprocess.run(command, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
        data = json.loads(result.stdout)
        self.duration = float(data["format"]["duration"])
        self.has_audio = bool(data.get("streams"))

    def _run_ffmpeg(self, command: list[str], start: float, end: float) -> None:
        # Unir stderr e stdout evita que um dos buffers encha e bloqueie o FFmpeg.
        # Também permite conservar as últimas mensagens para apresentar um erro útil.
        recent_output: deque[str] = deque(maxlen=30)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
        self.process = process
        assert process.stdout is not None

        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if line:
                    recent_output.append(line)
                if self.cancel_requested:
                    process.terminate()
                    break

                key, separator, raw_value = line.partition("=")
                if separator and key in {"out_time_us", "out_time_ms"}:
                    # Algumas versões emitem N/A no início. Isso é normal e deve
                    # apenas ser ignorado, não interromper a compressão.
                    try:
                        microseconds = int(raw_value)
                    except ValueError:
                        continue
                    fraction = min(1.0, max(0.0, microseconds / 1_000_000 / self.duration))
                    self.events.put(("progress", start + (end - start) * fraction))
                elif separator and key == "speed" and raw_value not in {"N/A", "0x"}:
                    self.events.put(("speed", raw_value))
        except Exception:
            if process.poll() is None:
                process.terminate()
            process.wait()
            raise

        return_code = process.wait()
        if return_code and not self.cancel_requested:
            diagnostic = next(
                (
                    line
                    for line in reversed(recent_output)
                    if "=" not in line or line.lower().startswith(("error", "failed", "invalid"))
                ),
                "O FFmpeg encerrou com erro.",
            )
            raise RuntimeError(diagnostic)

    @staticmethod
    def _scale_filter(resolution: str, source_height: int | None = None) -> str | None:
        heights = {"2160p (4K)": 2160, "1080p": 1080, "720p": 720, "480p": 480}
        height = 1080 if resolution == "Automática (recomendado)" and (source_height or 0) > 1080 else heights.get(resolution)
        return f"scale=-2:'min(ih,{height})'" if height else None

    @staticmethod
    def _find_program(name: str) -> str:
        path = shutil.which(name)
        if path:
            return path

        executable = f"{name}.exe" if os.name == "nt" else name
        project_dir = Path(__file__).resolve().parent
        local_candidates = (
            CompressorApp._user_ffmpeg_bin() / executable,
            project_dir / "ffmpeg" / "bin" / executable,
            project_dir / "bin" / executable,
            Path("C:/ffmpeg/bin") / executable,
            Path("C:/Program Files/ffmpeg/bin") / executable,
            Path.home() / "AppData/Local/Microsoft/WinGet/Links" / executable,
        )
        for candidate in local_candidates:
            if candidate.is_file():
                return str(candidate)

        # Builds baixadas do gyan.dev normalmente são extraídas nesta estrutura.
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            for candidate in downloads.glob(f"ffmpeg*/**/bin/{executable}"):
                if candidate.is_file():
                    return str(candidate)

        raise FileNotFoundError(
            f"{name} não foi encontrado. Extraia o FFmpeg na pasta do projeto como "
            "'ffmpeg\\bin' ou adicione a pasta 'bin' ao PATH do Windows."
        )

    def _cancel(self) -> None:
        self.cancel_requested = True
        self.status.set("Cancelando...")
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _offer_ffmpeg_install(self) -> None:
        install = messagebox.askyesno(
            "Componente necessário",
            "Para comprimir vídeos, o aplicativo precisa preparar o mecanismo FFmpeg.\n\n"
            "Deseja baixar e configurar automaticamente agora?\n\n"
            "O download tem aproximadamente 100 MB e será feito do site gyan.dev.",
        )
        if not install:
            self.status.set("O FFmpeg é necessário para analisar e comprimir vídeos.")
            return
        self.start_button["state"] = "disabled"
        self.progress.configure(mode="determinate", value=0)
        self.status.set("Baixando o mecanismo de vídeo...")
        threading.Thread(target=self._install_ffmpeg_worker, daemon=True).start()

    def _install_ffmpeg_worker(self) -> None:
        try:
            install_bin = self._user_ffmpeg_bin()
            install_bin.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="compressor_ffmpeg_") as temp_dir:
                archive = Path(temp_dir) / "ffmpeg.zip"
                request = urllib.request.Request(FFMPEG_DOWNLOAD_URL, headers={"User-Agent": "CompressorVideo/1.0"})
                with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as destination:
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    while chunk := response.read(1024 * 1024):
                        destination.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.events.put(("download_progress", downloaded * 100 / total))

                with zipfile.ZipFile(archive) as package:
                    members = {
                        Path(info.filename).name.lower(): info
                        for info in package.infolist()
                        if Path(info.filename).name.lower() in {"ffmpeg.exe", "ffprobe.exe"}
                        and "/bin/" in info.filename.replace("\\", "/").lower()
                    }
                    if not {"ffmpeg.exe", "ffprobe.exe"}.issubset(members):
                        raise RuntimeError("O pacote baixado não contém os arquivos esperados.")
                    for filename in ("ffmpeg.exe", "ffprobe.exe"):
                        with package.open(members[filename]) as source, (install_bin / filename).open("wb") as destination:
                            shutil.copyfileobj(source, destination)
            self.events.put(("ffmpeg_installed", None))
        except Exception as exc:
            self.events.put(("install_error", str(exc)))

    def _drain_events(self) -> None:
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "probed":
                    self.duration, size, width, height, self.has_audio = value  # type: ignore[misc]
                    self.video_height = height
                    minutes, seconds = divmod(round(self.duration), 60)
                    auto_note = "  •  Saída automática: 1080p" if height and height > 1080 else ""
                    self.details.set(
                        f"{width}×{height}  •  {minutes}:{seconds:02d}  •  {size / 1024**3:.2f} GB{auto_note}"
                    )
                    self.status.set("Pronto. O modo recomendado reduz o tempo sem perder boa qualidade visual.")
                elif event == "progress":
                    self._show_progress(float(value))
                elif event == "speed":
                    self.encoding_speed = str(value)
                elif event == "download_progress":
                    self.progress["value"] = value
                elif event == "status":
                    self.status.set(str(value))
                elif event == "missing_ffmpeg":
                    self._offer_ffmpeg_install()
                elif event == "ffmpeg_installed":
                    self.start_button["state"] = "normal"
                    self.progress["value"] = 0
                    self.status.set("Mecanismo instalado. Analisando o vídeo...")
                    source = Path(self.input_path.get())
                    if source.is_file():
                        threading.Thread(target=self._probe_worker, args=(source,), daemon=True).start()
                elif event == "install_error":
                    self.start_button["state"] = "normal"
                    self.progress["value"] = 0
                    self.status.set("Não foi possível preparar o mecanismo de vídeo.")
                    messagebox.showerror(
                        "Falha no download",
                        f"Não foi possível baixar o FFmpeg. Verifique sua conexão e tente novamente.\n\nDetalhes: {value}",
                    )
                elif event == "done":
                    output, actual_mb = value  # type: ignore[misc]
                    self.progress["value"] = 100
                    self.progress_info.set(f"100%  •  Concluído em {self._format_time(time.monotonic() - self.started_at)}")
                    self._finish_controls()
                    self.status.set(f"Concluído: {actual_mb:.1f} MB")
                    messagebox.showinfo("Compressão concluída", f"Arquivo salvo em:\n{output}\n\nTamanho: {actual_mb:.1f} MB")
                elif event == "cancelled":
                    self._finish_controls()
                    self.progress_info.set("Cancelado")
                    self.status.set("Compressão cancelada.")
                elif event == "error":
                    self._finish_controls()
                    self.status.set("Ocorreu um erro.")
                    messagebox.showerror("Erro", str(value))
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _finish_controls(self) -> None:
        self.process = None
        self.start_button["state"] = "normal"
        self.cancel_button["state"] = "disabled"

    def _show_progress(self, percent: float) -> None:
        self.progress["value"] = percent
        elapsed = max(0.0, time.monotonic() - self.started_at)
        parts = [f"{percent:.0f}%", f"Decorrido: {self._format_time(elapsed)}"]
        if percent >= 1 and elapsed >= 3:
            remaining = max(0.0, elapsed * (100 - percent) / percent)
            parts.append(f"Restante: cerca de {self._format_time(remaining)}")
        if self.encoding_speed:
            parts.append(f"Velocidade: {self.encoding_speed}")
        self.progress_info.set("  •  ".join(parts))

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, round(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}min"
        if minutes:
            return f"{minutes}min {secs:02d}s"
        return f"{secs}s"

    @staticmethod
    def _user_ffmpeg_bin() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData/Local"
        return base / "CompressorVideo" / "ffmpeg" / "bin"

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Sair?", "Uma compressão está em andamento. Deseja cancelar e sair?"):
                return
            self._cancel()
        self.destroy()


if __name__ == "__main__":
    CompressorApp().mainloop()
