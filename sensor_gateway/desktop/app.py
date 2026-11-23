from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .config_file import safe_configuration_status
from .controller import GatewayController, UiEvent


class SensorGatewayApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PlanTalk 센서 연결")
        self.geometry("900x720")
        self.minsize(820, 660)
        self.configure(bg="#edf3ee")
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.controller = GatewayController()
        self.port_by_label: dict[str, str] = {}
        self.zero_raw: Optional[float] = None
        self.reference_raw: Optional[float] = None
        self.pending_measurement: Optional[str] = None
        self.busy = False
        self.running = False

        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="아두이노를 USB로 연결해 주세요.")
        self.remote_var = tk.StringVar(value="확인 전")
        self.zero_var = tk.StringVar(value="측정 전")
        self.reference_var = tk.StringVar(value="측정 전")
        self.factor_var = tk.StringVar(value="저장 전")
        self.known_weight_var = tk.StringVar(value="1000")
        self.upload_var = tk.BooleanVar(value=True)
        self.metric_vars = {
            key: tk.StringVar(value="-")
            for key in (
                "weight_g",
                "raw_sensor_value",
                "soil_raw",
                "light_raw",
                "temperature_c",
                "humidity_percent",
                "captured_at",
                "sensor_status",
                "hx711_ready",
            )
        }

        self._configure_styles()
        self._build()
        self.after(150, self._poll_events)
        self.after(250, self.refresh_ports)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Page.TFrame", background="#edf3ee")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure(
            "Title.TLabel",
            background="#edf3ee",
            foreground="#153d29",
            font=("맑은 고딕", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#edf3ee",
            foreground="#5d7064",
            font=("맑은 고딕", 10),
        )
        style.configure(
            "Heading.TLabel",
            background="#ffffff",
            foreground="#153d29",
            font=("맑은 고딕", 12, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background="#ffffff",
            foreground="#34483b",
            font=("맑은 고딕", 9),
        )
        style.configure(
            "Muted.TLabel",
            background="#ffffff",
            foreground="#6c7d72",
            font=("맑은 고딕", 8),
        )
        style.configure(
            "Metric.TLabel",
            background="#ffffff",
            foreground="#1f7048",
            font=("맑은 고딕", 12, "bold"),
        )
        style.configure(
            "Primary.TButton",
            font=("맑은 고딕", 9, "bold"),
            padding=(12, 8),
        )
        style.configure("TNotebook", background="#edf3ee", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9), font=("맑은 고딕", 9))

    def _build(self) -> None:
        page = ttk.Frame(self, style="Page.TFrame", padding=24)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="PlanTalk 센서 연결", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            page,
            text="아두이노 연결부터 보정과 Supabase 저장까지 순서대로 진행합니다.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 16))

        notebook = ttk.Notebook(page)
        notebook.pack(fill="both", expand=True)
        self.connection_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=22)
        self.calibration_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=22)
        self.collection_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=22)
        notebook.add(self.connection_tab, text="1  연결 확인")
        notebook.add(self.calibration_tab, text="2  로드셀 보정")
        notebook.add(self.collection_tab, text="3  수집 시작")
        self.notebook = notebook

        self._build_connection_tab()
        self._build_calibration_tab()
        self._build_collection_tab()

        status = ttk.Label(
            page,
            textvariable=self.status_var,
            style="Subtitle.TLabel",
            anchor="w",
        )
        status.pack(fill="x", pady=(14, 0))

    def _build_connection_tab(self) -> None:
        tab = self.connection_tab
        ttk.Label(tab, text="아두이노 포트", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="Arduino IDE의 시리얼 모니터를 먼저 닫아야 합니다.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 12))

        row = ttk.Frame(tab, style="Panel.TFrame")
        row.pack(fill="x")
        self.port_combo = ttk.Combobox(
            row,
            textvariable=self.port_var,
            state="readonly",
            width=60,
        )
        self.port_combo.pack(side="left", fill="x", expand=True)
        self.refresh_button = ttk.Button(row, text="새로고침", command=self.refresh_ports)
        self.refresh_button.pack(side="left", padx=(8, 0))
        self.connect_button = ttk.Button(
            tab,
            text="센서값 1개 받아 연결 확인",
            style="Primary.TButton",
            command=self.test_sensor,
        )
        self.connect_button.pack(anchor="w", pady=(14, 24))

        ttk.Separator(tab).pack(fill="x", pady=(0, 20))
        ttk.Label(tab, text="Supabase 설정", style="Heading.TLabel").pack(anchor="w")
        config_status = safe_configuration_status()
        configured = all(
            config_status[key] for key in ("supabase", "login", "plant")
        )
        self.remote_var.set("설정됨" if configured else "설정 누락")
        ttk.Label(tab, textvariable=self.remote_var, style="Metric.TLabel").pack(
            anchor="w", pady=(8, 8)
        )
        self.remote_button = ttk.Button(
            tab,
            text="로그인만 시험",
            command=self.test_remote,
        )
        self.remote_button.pack(anchor="w")

    def _build_calibration_tab(self) -> None:
        tab = self.calibration_tab
        ttk.Label(tab, text="1. 영점 측정", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            tab,
            text="저울 위의 물건을 모두 치운 뒤 측정합니다. 원본값 20개의 중앙값을 사용합니다.",
            style="Muted.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(3, 8))
        self.zero_button = ttk.Button(
            tab,
            text="영점 측정",
            command=lambda: self.start_measurement("zero"),
        )
        self.zero_button.pack(anchor="w")
        ttk.Label(tab, textvariable=self.zero_var, style="Metric.TLabel").pack(
            anchor="w", pady=(8, 22)
        )

        ttk.Label(tab, text="2. 기준 추 측정", style="Heading.TLabel").pack(anchor="w")
        weight_row = ttk.Frame(tab, style="Panel.TFrame")
        weight_row.pack(anchor="w", pady=(8, 8))
        ttk.Label(weight_row, text="기준 추 무게", style="Body.TLabel").pack(side="left")
        ttk.Entry(weight_row, textvariable=self.known_weight_var, width=12).pack(
            side="left", padx=(10, 5)
        )
        ttk.Label(weight_row, text="g", style="Body.TLabel").pack(side="left")
        self.reference_button = ttk.Button(
            tab,
            text="기준 추 측정 및 보정 저장",
            command=lambda: self.start_measurement("reference"),
        )
        self.reference_button.pack(anchor="w")
        ttk.Label(tab, textvariable=self.reference_var, style="Metric.TLabel").pack(
            anchor="w", pady=(8, 6)
        )
        ttk.Label(tab, textvariable=self.factor_var, style="Body.TLabel").pack(anchor="w")

    def _build_collection_tab(self) -> None:
        tab = self.collection_tab
        control = ttk.Frame(tab, style="Panel.TFrame")
        control.pack(fill="x")
        ttk.Checkbutton(
            control,
            text="Supabase에도 전송",
            variable=self.upload_var,
        ).pack(side="left")
        self.start_button = ttk.Button(
            control,
            text="수집 시작",
            style="Primary.TButton",
            command=self.start_collection,
        )
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(
            control,
            text="중지",
            command=self.stop_collection,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 8))

        metrics = ttk.Frame(tab, style="Panel.TFrame")
        metrics.pack(fill="x", pady=(20, 12))
        labels = (
            ("weight_g", "보정 무게", "g"),
            ("raw_sensor_value", "로드셀 원본", ""),
            ("soil_raw", "토양 원본", ""),
            ("light_raw", "조도 원본", ""),
            ("temperature_c", "온도", "°C"),
            ("humidity_percent", "습도", "%"),
            ("sensor_status", "센서 상태", ""),
            ("hx711_ready", "HX711 준비", ""),
        )
        for index, (key, label, unit) in enumerate(labels):
            cell = ttk.Frame(metrics, style="Panel.TFrame", padding=(8, 6))
            cell.grid(row=index // 3, column=index % 3, sticky="ew")
            ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
            value_row = ttk.Frame(cell, style="Panel.TFrame")
            value_row.pack(fill="x")
            ttk.Label(
                value_row,
                textvariable=self.metric_vars[key],
                style="Metric.TLabel",
            ).pack(side="left")
            if unit:
                ttk.Label(value_row, text=f" {unit}", style="Body.TLabel").pack(
                    side="left"
                )
        for column in range(3):
            metrics.columnconfigure(column, weight=1)

        ttk.Label(tab, text="실행 기록", style="Heading.TLabel").pack(anchor="w")
        self.log_text = tk.Text(
            tab,
            height=12,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 9),
            bg="#f7faf7",
            fg="#263a2d",
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

    def selected_port(self) -> Optional[str]:
        return self.port_by_label.get(self.port_var.get())

    def refresh_ports(self) -> None:
        try:
            ports = self.controller.available_ports()
        except Exception as exc:
            self._show_error(str(exc))
            return
        self.port_by_label = {
            f"{item['device']} — {item['description'] or '설명 없음'}": str(
                item["device"]
            )
            for item in ports
        }
        labels = list(self.port_by_label)
        self.port_combo["values"] = labels
        if labels:
            self.port_var.set(labels[0])
            self.status_var.set(f"시리얼 포트 {len(labels)}개를 찾았습니다.")
        else:
            self.port_var.set("")
            self.status_var.set("아두이노 포트를 찾지 못했습니다.")

    def _require_port(self) -> Optional[str]:
        port = self.selected_port()
        if not port:
            messagebox.showwarning("포트 필요", "아두이노 COM 포트를 선택해 주세요.")
        return port

    def test_sensor(self) -> None:
        port = self._require_port()
        if port and self.controller.run_async(self.controller.measure_raw, port, 1):
            self.pending_measurement = "connection"
            self._set_busy(True, "센서값을 기다리는 중입니다.")

    def test_remote(self) -> None:
        if self.controller.run_async(self.controller.test_remote):
            self._set_busy(True, "Supabase 로그인을 확인하는 중입니다.")

    def start_measurement(self, kind: str) -> None:
        port = self._require_port()
        if not port:
            return
        if kind == "reference" and self.zero_raw is None:
            messagebox.showwarning("영점 필요", "먼저 영점 측정을 완료해 주세요.")
            return
        if kind == "reference":
            try:
                if float(self.known_weight_var.get()) <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("무게 확인", "기준 추 무게를 g 단위로 입력해 주세요.")
                return
        if self.controller.run_async(self.controller.measure_raw, port, 20):
            self.pending_measurement = kind
            label = "영점" if kind == "zero" else "기준 추"
            self._set_busy(True, f"{label} 원본값 20개를 측정하는 중입니다.")

    def start_collection(self) -> None:
        port = self._require_port()
        if not port:
            return
        if self.upload_var.get() and not safe_configuration_status()["calibration"]:
            messagebox.showwarning(
                "보정 필요",
                "Supabase 전송 전 로드셀 보정을 완료해 주세요.",
            )
            return
        if self.controller.start_collection(port, self.upload_var.get()):
            self._set_busy(True, "센서 수집을 시작하는 중입니다.")

    def stop_collection(self) -> None:
        self.controller.stop_collection()
        self.stop_button.configure(state="disabled")

    def _set_busy(self, busy: bool, message: Optional[str] = None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (
            self.connect_button,
            self.remote_button,
            self.zero_button,
            self.reference_button,
            self.start_button,
            self.refresh_button,
        ):
            button.configure(state=state)
        if message:
            self.status_var.set(message)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _handle_event(self, event: UiEvent) -> None:
        if event.kind == "log":
            self._append_log(str(event.payload))
        elif event.kind == "sample":
            payload = dict(event.payload)  # type: ignore[arg-type]
            for key, variable in self.metric_vars.items():
                if key in payload:
                    value = payload.get(key)
                    variable.set("-" if value is None else str(value))
        elif event.kind == "measurement":
            value = float(event.payload)
            if self.pending_measurement == "zero":
                self.zero_raw = value
                self.zero_var.set(f"영점 중앙값: {value:.3f}")
            elif self.pending_measurement == "reference":
                self.reference_raw = value
                self.reference_var.set(f"기준 추 중앙값: {value:.3f}")
                assert self.zero_raw is not None
                result = self.controller.save_calibration(
                    zero_raw=self.zero_raw,
                    loaded_raw=value,
                    known_weight_g=float(self.known_weight_var.get()),
                )
                self.factor_var.set(
                    "환산계수: " f"{result['grams_per_unit']:.12g} g/raw"
                )
            elif self.pending_measurement == "connection":
                self._append_log(f"센서 연결 확인: 로드셀 원본값 {value:.3f}")
                messagebox.showinfo("연결 성공", "아두이노 JSON 센서값을 정상 수신했습니다.")
            self.pending_measurement = None
        elif event.kind == "remote_ok":
            self.remote_var.set("로그인 확인 완료")
            messagebox.showinfo("Supabase 연결", "센서 테스트 계정 로그인이 정상입니다.")
        elif event.kind == "running":
            payload = dict(event.payload)  # type: ignore[arg-type]
            self.running = True
            self.stop_button.configure(state="normal")
            destination = "로컬 + Supabase" if payload["upload"] else "로컬"
            self.status_var.set(f"{payload['port']}에서 {destination} 수집 중입니다.")
            self._append_log(f"수집 시작 — {destination}")
        elif event.kind == "summary":
            self._append_log(f"수집 결과: {event.payload}")
        elif event.kind == "error":
            self._show_error(str(event.payload))
        elif event.kind == "idle":
            self.running = False
            self.stop_button.configure(state="disabled")
            self._set_busy(False, "대기 중입니다.")

    def _show_error(self, message: str) -> None:
        self.status_var.set("오류가 발생했습니다.")
        self._append_log(f"오류: {message}") if hasattr(self, "log_text") else None
        messagebox.showerror("PlanTalk 센서 연결 오류", message)

    def _poll_events(self) -> None:
        for event in self.controller.drain_events():
            self._handle_event(event)
        self.after(150, self._poll_events)

    def _close(self) -> None:
        if self.running:
            self.controller.stop_collection()
        self.destroy()


def main() -> None:
    app = SensorGatewayApp()
    app.mainloop()


if __name__ == "__main__":
    main()

