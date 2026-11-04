"""Simple desktop front end for the Luma-Winslow Folio Engine."""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from lwfe_archive import create_archive
from lwfe_engine import ENGINE_VERSION, LWFEError, load_library, output_path_for, render_sound

APP_VERSION = "0.1.3"
PROJECT_ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = PROJECT_ROOT / "lwfe.json"

try:
    import winsound
except ImportError:  # The program can still render WAVs on non-Windows systems.
    winsound = None


class LWFEApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Luma-Winslow Folio Engine  |  LWFE {APP_VERSION}")
        self.root.geometry("760x520")
        self.root.minsize(620, 440)
        self.library: dict = {}
        self.sounds: list[dict] = []
        self.selected_sound: dict | None = None

        # This is the one working directory for this application run.  It is
        # assigned only after the startup snapshot has been created safely.
        self.session_archive: Path | None = None
        self.archive_error: str | None = None

        self._build_menu()
        self._build_ui()

        # Snapshot source/folio/current sounds first.  All subsequent RENDER
        # and PLAY operations in this run use this directory, never PROJECT_ROOT.
        try:
            self.session_archive = create_archive(PROJECT_ROOT, APP_VERSION)
        except Exception as exc:
            self.archive_error = str(exc)

        self.reload_library(show_message=False)
        if self.session_archive is not None:
            self.status_var.set(
                f"Session ready. New renders will be saved in: "
                f"{self.session_archive.relative_to(PROJECT_ROOT)}"
            )
        else:
            self.status_var.set(
                "ARCHIVE ERROR — rendering is disabled because a safe session "
                f"workspace could not be created: {self.archive_error}"
            )

        self.root.bind("<Escape>", lambda _event: self.stop_playback())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        project_menu = tk.Menu(menu_bar, tearoff=False)
        project_menu.add_command(label="Reload lwfe.json", command=self.reload_library, accelerator="F5")
        project_menu.add_command(
            label="Create additional snapshot (does not change this session)",
            command=self.archive_now,
        )
        project_menu.add_separator()
        project_menu.add_command(label="Exit", command=self.close)
        menu_bar.add_cascade(label="Project", menu=project_menu)
        self.root.config(menu=menu_bar)
        self.root.bind("<F5>", lambda _event: self.reload_library())

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="Luma-Winslow Folio Engine", font=("Segoe UI", 17, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(
            outer,
            text=(
                "Choose a sound folio. PLAY uses the WAV in this run's archive; "
                "RENDER paints a new WAV into that same archive."
            ),
            wraplength=700,
        )
        subtitle.pack(anchor="w", pady=(4, 14))

        list_frame = ttk.LabelFrame(outer, text="Sound folios in lwfe.json", padding=10)
        list_frame.pack(fill="both", expand=True)
        self.sound_list = tk.Listbox(list_frame, height=11, font=("Segoe UI", 11), activestyle="dotbox")
        self.sound_list.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.sound_list.yview)
        scroll.pack(side="right", fill="y")
        self.sound_list.configure(yscrollcommand=scroll.set)
        self.sound_list.bind("<<ListboxSelect>>", self.on_select)

        self.description_var = tk.StringVar(value="Select a sound to see its description.")
        ttk.Label(outer, textvariable=self.description_var, wraplength=700).pack(anchor="w", pady=(10, 12))

        actions = ttk.Frame(outer)
        actions.pack(anchor="w")
        self.play_button = ttk.Button(actions, text="PLAY", command=self.play_selected, width=16, state="disabled")
        self.play_button.pack(side="left", padx=(0, 8))
        self.render_button = ttk.Button(actions, text="RENDER", command=self.render_selected, width=16, state="disabled")
        self.render_button.pack(side="left")

        self.status_var = tk.StringVar(value="Creating this run's archive workspace...")
        ttk.Separator(outer).pack(fill="x", pady=(15, 8))
        ttk.Label(outer, textvariable=self.status_var, wraplength=700).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                f"Engine {ENGINE_VERSION}  •  App {APP_VERSION}  •  "
                "WAV masters: 48 kHz / 16-bit mono"
            ),
            foreground="#666666",
        ).pack(anchor="w", pady=(5, 0))

    def _output_path(self, sound: dict) -> Path | None:
        if self.session_archive is None:
            return None
        return output_path_for(sound, PROJECT_ROOT, output_root=self.session_archive)

    def reload_library(self, show_message: bool = True) -> None:
        try:
            self.library = load_library(LIBRARY_PATH)
            self.sounds = self.library["sounds"]
        except LWFEError as exc:
            messagebox.showerror("LWFE sound folio error", str(exc))
            self.status_var.set(str(exc))
            self.render_button.configure(state="disabled")
            self.play_button.configure(state="disabled")
            return

        self.sound_list.delete(0, tk.END)
        for sound in self.sounds:
            self.sound_list.insert(tk.END, sound.get("name", sound.get("id", "Unnamed sound")))
        self.selected_sound = None
        self.description_var.set("Select a sound to see its description.")
        self.play_button.configure(state="disabled")
        self.render_button.configure(state="disabled")
        self.status_var.set(f"Loaded {len(self.sounds)} sound folios from lwfe.json.")
        if show_message:
            messagebox.showinfo("LWFE", f"Loaded {len(self.sounds)} sound folios.")

    def on_select(self, _event: object = None) -> None:
        selection = self.sound_list.curselection()
        if not selection:
            self.selected_sound = None
            self.play_button.configure(state="disabled")
            self.render_button.configure(state="disabled")
            return

        self.selected_sound = self.sounds[int(selection[0])]
        description = self.selected_sound.get("description", "No description supplied.")
        self.description_var.set(description)

        output = self._output_path(self.selected_sound)
        if output is None:
            self.render_button.configure(state="disabled")
            self.play_button.configure(state="disabled")
            self.status_var.set(
                "Rendering is disabled: this run has no archive workspace. "
                f"{self.archive_error or ''}"
            )
            return

        self.render_button.configure(state="normal")
        self.refresh_play_button()
        if output.exists():
            self.status_var.set(f"Ready to play this session's render: {output.relative_to(self.session_archive)}")
        else:
            self.status_var.set("No render in this session yet. Select RENDER to paint it here.")

    def refresh_play_button(self) -> None:
        output = self._output_path(self.selected_sound) if self.selected_sound is not None else None
        exists = output is not None and output.is_file()
        self.play_button.configure(state="normal" if exists and winsound is not None else "disabled")
        if exists and winsound is None:
            self.status_var.set(
                "WAV exists in this session's archive. Playback needs Windows or a configured audio player."
            )

    def render_selected(self) -> None:
        if self.selected_sound is None:
            return
        if self.session_archive is None:
            messagebox.showerror(
                "LWFE archive error",
                "No session archive was created. Rendering is disabled to protect the main sounds folder.",
            )
            return

        self.render_button.configure(state="disabled")
        self.status_var.set("Painting sound into this run's archive...")
        self.root.update_idletasks()
        try:
            destination = render_sound(
                self.selected_sound,
                PROJECT_ROOT,
                output_root=self.session_archive,
            )
        except (LWFEError, OSError, ValueError, TypeError) as exc:
            messagebox.showerror("LWFE render error", str(exc))
            self.status_var.set(f"Render failed: {exc}")
        else:
            self.status_var.set(
                f"Rendered into this session: {destination.relative_to(self.session_archive)}"
            )
            self.refresh_play_button()
        finally:
            self.render_button.configure(state="normal" if self.session_archive is not None else "disabled")

    def play_selected(self) -> None:
        if self.selected_sound is None or winsound is None:
            return
        path = self._output_path(self.selected_sound)
        if path is None or not path.is_file():
            self.refresh_play_button()
            return
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            self.status_var.set(f"Playing this session's render: {path.name}  (press Esc to stop)")
        except RuntimeError as exc:
            messagebox.showerror("Playback error", str(exc))

    def stop_playback(self) -> None:
        if winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                pass
        if self.selected_sound is not None:
            path = self._output_path(self.selected_sound)
            if path is not None:
                self.status_var.set(f"Stopped. Session selection: {path.name}")
                return
        self.status_var.set("Playback stopped.")

    def archive_now(self) -> None:
        try:
            archive = create_archive(PROJECT_ROOT, APP_VERSION)
        except OSError as exc:
            messagebox.showerror("Snapshot error", str(exc))
            return
        active = self.session_archive.name if self.session_archive is not None else "unavailable"
        self.status_var.set(
            f"Additional snapshot saved: {archive.name}. "
            f"Current render workspace remains: {active}"
        )

    def close(self) -> None:
        self.stop_playback()
        self.root.destroy()


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"LWFE could not open its desktop window: {exc}", file=sys.stderr)
        return 1
    LWFEApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
