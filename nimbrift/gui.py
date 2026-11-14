"""Small desktop frontend; all network work runs outside the UI thread."""

import queue
import threading
from pathlib import Path

from .model import Connection, Direction, Progress, Transfer, TransferCancelled
from .service import TransferService


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print("Tkinter is unavailable in this Python. Install a Python build with Tk support.")
        return 1

    root = tk.Tk()
    root.title("Nimbrift")
    root.minsize(560, 430)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    values = {
        "Host": tk.StringVar(),
        "Username": tk.StringVar(),
        "Port": tk.StringVar(value="22"),
        "Private key": tk.StringVar(),
        "Known hosts": tk.StringVar(),
        "Password": tk.StringVar(),
        "Source": tk.StringVar(),
        "Destination": tk.StringVar(),
    }
    direction = tk.StringVar(value=Direction.UPLOAD.value)
    overwrite = tk.BooleanVar(value=False)
    status = tk.StringVar(value="Ready")
    events: queue.Queue[tuple[str, object]] = queue.Queue()
    cancel = threading.Event()
    worker: threading.Thread | None = None

    def row(label: str, index: int, *, secret: bool = False, browse=None) -> None:
        ttk.Label(frame, text=label).grid(row=index, column=0, sticky="w", pady=4)
        entry = ttk.Entry(frame, textvariable=values[label], show="*" if secret else "")
        entry.grid(row=index, column=1, sticky="ew", padx=8, pady=4)
        if browse:
            ttk.Button(frame, text="Browse", command=browse).grid(row=index, column=2, pady=4)

    def choose_source() -> None:
        if direction.get() == Direction.UPLOAD.value:
            selected = filedialog.askopenfilename(title="Choose a file to upload")
            if selected:
                values["Source"].set(selected)

    def choose_source_folder() -> None:
        if direction.get() == Direction.UPLOAD.value:
            selected = filedialog.askdirectory(title="Choose a folder to upload")
            if selected:
                values["Source"].set(selected)

    def choose_destination() -> None:
        if direction.get() == Direction.DOWNLOAD.value:
            selected = filedialog.askdirectory(title="Choose download directory")
            if selected:
                values["Destination"].set(selected)

    ttk.Label(frame, text="Direction").grid(row=0, column=0, sticky="w")
    selector = ttk.Combobox(frame, textvariable=direction, values=[d.value for d in Direction], state="readonly")
    selector.grid(row=0, column=1, sticky="ew", padx=8)
    row("Host", 1)
    row("Username", 2)
    row("Port", 3)
    row("Private key", 4, browse=lambda: values["Private key"].set(filedialog.askopenfilename() or values["Private key"].get()))
    row("Known hosts", 5, browse=lambda: values["Known hosts"].set(filedialog.askopenfilename() or values["Known hosts"].get()))
    row("Password", 6, secret=True)
    row("Source", 7, browse=choose_source)
    row("Destination", 8, browse=choose_destination)
    ttk.Button(frame, text="Upload folder", command=choose_source_folder).grid(row=9, column=2, pady=4)
    ttk.Checkbutton(frame, text="Overwrite existing files", variable=overwrite).grid(row=9, column=1, sticky="w", pady=5)
    ttk.Label(frame, text="SSH host key must already be in known_hosts.", wraplength=480).grid(row=10, column=0, columnspan=3, sticky="w", pady=5)
    bar = ttk.Progressbar(frame, maximum=100)
    bar.grid(row=11, column=0, columnspan=3, sticky="ew", pady=8)
    ttk.Label(frame, textvariable=status, wraplength=500).grid(row=12, column=0, columnspan=3, sticky="w")

    def start() -> None:
        nonlocal worker
        try:
            connection = Connection(
                host=values["Host"].get(),
                username=values["Username"].get(),
                port=int(values["Port"].get()),
                key_file=Path(values["Private key"].get()) if values["Private key"].get() else None,
                known_hosts=Path(values["Known hosts"].get()) if values["Known hosts"].get() else None,
                password=values["Password"].get() or None,
            )
            request = Transfer(Direction(direction.get()), values["Source"].get(), values["Destination"].get(), overwrite.get())
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        cancel.clear()
        bar["value"] = 0
        status.set("Connecting…")
        start_button["state"] = "disabled"
        cancel_button["state"] = "normal"

        def run() -> None:
            try:
                TransferService().run(connection, request, lambda p: events.put(("progress", p)), cancel)
                events.put(("done", "Transfer complete"))
            except TransferCancelled:
                events.put(("done", "Transfer cancelled"))
            except Exception as exc:
                events.put(("error", str(exc)))

        worker = threading.Thread(target=run, daemon=True)
        worker.start()

    buttons = ttk.Frame(frame)
    buttons.grid(row=13, column=0, columnspan=3, sticky="e", pady=12)
    start_button = ttk.Button(buttons, text="Start transfer", command=start)
    start_button.pack(side="left", padx=5)
    cancel_button = ttk.Button(buttons, text="Cancel", command=lambda: cancel.set(), state="disabled")
    cancel_button.pack(side="left")

    def poll() -> None:
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "progress":
                    item = value
                    bar["value"] = 100 if item.total == 0 else item.transferred * 100 / item.total
                    status.set(f"{item.path}: {item.transferred:,} / {item.total:,} bytes")
                else:
                    status.set(str(value))
                    start_button["state"] = "normal"
                    cancel_button["state"] = "disabled"
                    if kind == "error":
                        messagebox.showerror("Transfer failed", str(value))
        except queue.Empty:
            pass
        root.after(100, poll)

    root.after(100, poll)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
