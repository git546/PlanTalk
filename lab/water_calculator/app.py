from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .engine import LabInput, LabResult, TuningProfile, calculate

APP_DIR = Path(__file__).resolve().parent
SESSION_DIR = APP_DIR / "sessions"

INPUT_FIELDS = (
    ("period_days", "측정 기간", "일", "7"),
    ("start_pot_weight_g", "시작 화분 무게", "g", "3800"),
    ("end_pot_weight_g", "현재 화분 무게", "g", "3550"),
    ("water_added_ml", "누적 급수량", "mL", "500"),
    ("drainage_ml", "누적 배수량", "mL", "100"),
    ("target_wet_weight_g", "젖은 목표 무게", "g", "3800"),
    ("watering_trigger_weight_g", "물주기 기준 무게", "g", "3300"),
    ("max_single_watering_ml", "1회 최대 급수량", "mL", "450"),
)

PROFILE_FIELDS = (
    ("water_density_g_per_ml", "물 밀도", "g/mL", "1.0"),
    ("loss_scale", "손실 보정 배수", "배", "1.0"),
    ("loss_bias_ml", "손실 보정 편향", "mL", "0.0"),
    ("recommendation_scale", "권장 급수 보정 배수", "배", "1.0"),
    ("trigger_margin_g", "물주기 기준 마진", "g", "0.0"),
)

RESULT_ROWS = (
    ("status", "판정"),
    ("confidence", "신뢰도"),
    ("estimated_water_loss_ml", "기간 수분 손실"),
    ("average_daily_loss_ml", "하루 평균 손실"),
    ("refill_to_target_ml", "목표까지 부족량"),
    ("recommended_water_now_ml", "현재 권장 급수량"),
    ("estimated_days_until_watering", "예상 남은 일수"),
    ("drainage_ratio_percent", "배수율"),
)

STATUS_LABELS = {
    "hydrated": "충분함",
    "monitor": "관찰",
    "water_soon": "곧 물주기",
    "water_now": "지금 물주기",
}


class WaterCalculatorLab(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PlanTalk 수분 계산 실험실")
        self.geometry("1180x820")
        self.minsize(1024, 700)
        self.configure(bg="#eef2ee")

        self.input_vars: dict[str, tk.StringVar] = {}
        self.profile_vars: dict[str, tk.StringVar] = {}
        self.result_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-") for key, _ in RESULT_ROWS
        }
        self.profile_name = tk.StringVar(value="기본값")
        self.profile_version = tk.StringVar(value="1")
        self.note_var = tk.StringVar()
        self.comparison_var = tk.StringVar(value="기본 프로필과 같은 결과입니다.")
        self.status_var = tk.StringVar(value="측정값을 입력하고 계산을 실행하세요.")
        self.last_input: LabInput | None = None
        self.last_profile: TuningProfile | None = None
        self.last_result: LabResult | None = None
        self.last_baseline: LabResult | None = None

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Page.TFrame", background="#eef2ee")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#eef2ee", foreground="#173d29", font=("맑은 고딕", 22, "bold"))
        style.configure("Subtitle.TLabel", background="#eef2ee", foreground="#617067", font=("맑은 고딕", 10))
        style.configure("Heading.TLabel", background="#ffffff", foreground="#173d29", font=("맑은 고딕", 12, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#415248", font=("맑은 고딕", 9))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#738178", font=("맑은 고딕", 8))
        style.configure("ResultValue.TLabel", background="#ffffff", foreground="#1f6f47", font=("맑은 고딕", 10, "bold"))
        style.configure("Primary.TButton", font=("맑은 고딕", 10, "bold"), padding=(16, 10))
        style.configure("Secondary.TButton", font=("맑은 고딕", 9), padding=(12, 8))
        style.configure("Status.TLabel", background="#e5f1e8", foreground="#2b6344", font=("맑은 고딕", 9), padding=10)

    def _build_ui(self) -> None:
        page = ttk.Frame(self, style="Page.TFrame", padding=24)
        page.pack(fill="both", expand=True)

        ttk.Label(page, text="수분 계산 실험실", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            text="앱·DB와 분리된 실험용 프로그램입니다. 입력과 보정 계수를 저장해 반복 실험을 비교하세요.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 16))

        content = ttk.Frame(page, style="Page.TFrame")
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)

        input_panel = self._panel(content, 0, "1. 측정값")
        self._build_fields(input_panel, INPUT_FIELDS, self.input_vars)

        profile_panel = self._panel(content, 1, "2. 실험 보정")
        self._build_profile(profile_panel)

        result_panel = self._panel(content, 2, "3. 결과")
        self._build_results(result_panel)

        footer = ttk.Frame(page, style="Page.TFrame")
        footer.pack(fill="x", pady=(16, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="계산 실행", style="Primary.TButton", command=self._run_calculation).pack(side="right", padx=(12, 0))

    def _panel(self, parent: ttk.Frame, column: int, title: str) -> ttk.Frame:
        outer = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        outer.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))
        ttk.Label(outer, text=title, style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        return outer

    def _build_fields(
        self,
        parent: ttk.Frame,
        fields: tuple[tuple[str, str, str, str], ...],
        variables: dict[str, tk.StringVar],
    ) -> None:
        for key, label, unit, default in fields:
            row = ttk.Frame(parent, style="Panel.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="Body.TLabel").pack(anchor="w")
            value_row = ttk.Frame(row, style="Panel.TFrame")
            value_row.pack(fill="x", pady=(3, 0))
            var = tk.StringVar(value=default)
            variables[key] = var
            ttk.Entry(value_row, textvariable=var).pack(side="left", fill="x", expand=True)
            ttk.Label(value_row, text=unit, width=6, anchor="e", style="Muted.TLabel").pack(side="right", padx=(6, 0))

    def _build_profile(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="프로필 이름", style="Body.TLabel").pack(anchor="w")
        ttk.Entry(parent, textvariable=self.profile_name).pack(fill="x", pady=(3, 8))

        version_row = ttk.Frame(parent, style="Panel.TFrame")
        version_row.pack(fill="x", pady=(0, 6))
        ttk.Label(version_row, text="버전", style="Body.TLabel").pack(side="left")
        ttk.Entry(version_row, textvariable=self.profile_version, width=8).pack(side="right")

        self._build_fields(parent, PROFILE_FIELDS, self.profile_vars)

        button_row = ttk.Frame(parent, style="Panel.TFrame")
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="프로필 불러오기", style="Secondary.TButton", command=self._load_profile).pack(fill="x", pady=3)
        ttk.Button(button_row, text="프로필 저장", style="Secondary.TButton", command=self._save_profile).pack(fill="x", pady=3)
        ttk.Button(button_row, text="기본값 복원", style="Secondary.TButton", command=self._reset_profile).pack(fill="x", pady=3)

    def _build_results(self, parent: ttk.Frame) -> None:
        for key, label in RESULT_ROWS:
            row = ttk.Frame(parent, style="Panel.TFrame")
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=label, style="Body.TLabel").pack(side="left")
            ttk.Label(row, textvariable=self.result_vars[key], style="ResultValue.TLabel").pack(side="right")

        ttk.Separator(parent).pack(fill="x", pady=12)
        ttk.Label(parent, text="기본값 대비", style="Body.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            textvariable=self.comparison_var,
            style="Muted.TLabel",
            wraplength=300,
            justify="left",
        ).pack(anchor="w", fill="x", pady=(4, 12))

        ttk.Label(parent, text="실험 메모", style="Body.TLabel").pack(anchor="w")
        ttk.Entry(parent, textvariable=self.note_var).pack(fill="x", pady=(4, 10))
        ttk.Button(parent, text="세션 JSON 저장", style="Secondary.TButton", command=self._save_session).pack(fill="x")

        ttk.Label(parent, text="경고 및 확인 사항", style="Body.TLabel").pack(anchor="w", pady=(14, 4))
        self.warning_text = tk.Text(
            parent,
            height=8,
            wrap="word",
            background="#f6f8f6",
            foreground="#5a4b25",
            relief="flat",
            padx=10,
            pady=8,
            font=("맑은 고딕", 9),
            state="disabled",
        )
        self.warning_text.pack(fill="both", expand=True)

    @staticmethod
    def _number(value: str, label: str, *, optional: bool = False) -> float | None:
        value = value.strip()
        if optional and not value:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{label}에 숫자를 입력해 주세요.") from exc

    def _read_input(self) -> LabInput:
        labels = {key: label for key, label, _, _ in INPUT_FIELDS}
        values = {
            key: self._number(var.get(), labels[key], optional=key == "max_single_watering_ml")
            for key, var in self.input_vars.items()
        }
        return LabInput(**values)  # type: ignore[arg-type]

    def _read_profile(self) -> TuningProfile:
        labels = {key: label for key, label, _, _ in PROFILE_FIELDS}
        values = {
            key: self._number(var.get(), labels[key])
            for key, var in self.profile_vars.items()
        }
        try:
            version = int(self.profile_version.get().strip())
        except ValueError as exc:
            raise ValueError("프로필 버전은 정수로 입력해 주세요.") from exc
        return TuningProfile(
            name=self.profile_name.get().strip(),
            version=version,
            **values,  # type: ignore[arg-type]
        )

    def _run_calculation(self) -> None:
        try:
            input_data = self._read_input()
            profile = self._read_profile()
            baseline = calculate(input_data, TuningProfile())
            result = calculate(input_data, profile)
        except ValueError as exc:
            messagebox.showerror("입력 확인", str(exc), parent=self)
            self.status_var.set(str(exc))
            return

        self.last_input = input_data
        self.last_profile = profile
        self.last_result = result
        self.last_baseline = baseline
        self._render_result(result)
        self._render_comparison(baseline, result)
        self.status_var.set(f"{profile.name} v{profile.version} 기준으로 계산했습니다.")

    def _render_result(self, result: LabResult) -> None:
        units = {
            "estimated_water_loss_ml": " mL",
            "average_daily_loss_ml": " mL/일",
            "refill_to_target_ml": " mL",
            "recommended_water_now_ml": " mL",
            "estimated_days_until_watering": " 일",
            "drainage_ratio_percent": "%",
        }
        result_dict = result.to_dict()
        for key, _ in RESULT_ROWS:
            value = result_dict[key]
            if key == "status":
                text = STATUS_LABELS.get(str(value), str(value))
            elif key == "confidence":
                text = {"high": "높음", "medium": "보통", "low": "낮음"}.get(str(value), str(value))
            elif value is None:
                text = "계산 불가"
            else:
                text = f"{value}{units.get(key, '')}"
            self.result_vars[key].set(text)

        warning_text = "\n\n".join(result.warnings) if result.warnings else "특이 경고가 없습니다."
        self.warning_text.configure(state="normal")
        self.warning_text.delete("1.0", "end")
        self.warning_text.insert("1.0", warning_text)
        self.warning_text.configure(state="disabled")

    def _render_comparison(self, baseline: LabResult, result: LabResult) -> None:
        loss_delta = result.estimated_water_loss_ml - baseline.estimated_water_loss_ml
        daily_delta = result.average_daily_loss_ml - baseline.average_daily_loss_ml
        recommendation_delta = (
            result.recommended_water_now_ml - baseline.recommended_water_now_ml
        )
        self.comparison_var.set(
            f"손실량 {loss_delta:+.2f}mL · 하루 평균 {daily_delta:+.2f}mL · "
            f"권장 급수 {recommendation_delta:+.2f}mL"
        )

    def _reset_profile(self) -> None:
        default = TuningProfile()
        self.profile_name.set(default.name)
        self.profile_version.set(str(default.version))
        for key, _, _, _ in PROFILE_FIELDS:
            self.profile_vars[key].set(str(getattr(default, key)))
        self.status_var.set("보정 계수를 백엔드 v1과 같은 기본값으로 복원했습니다.")

    def _load_profile(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="실험 프로필 불러오기",
            initialdir=APP_DIR,
            filetypes=(("JSON", "*.json"), ("모든 파일", "*.*")),
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            profile = TuningProfile(**data)
            profile.validate()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            messagebox.showerror("불러오기 실패", str(exc), parent=self)
            return
        self.profile_name.set(profile.name)
        self.profile_version.set(str(profile.version))
        for key, _, _, _ in PROFILE_FIELDS:
            self.profile_vars[key].set(str(getattr(profile, key)))
        self.status_var.set(f"{profile.name} v{profile.version} 프로필을 불러왔습니다.")

    def _save_profile(self) -> None:
        try:
            profile = self._read_profile()
            profile.validate()
        except ValueError as exc:
            messagebox.showerror("프로필 확인", str(exc), parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="실험 프로필 저장",
            initialdir=APP_DIR,
            initialfile="tuning-profile.json",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"),),
        )
        if not path:
            return
        Path(path).write_text(
            json.dumps(asdict(profile), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.status_var.set(f"프로필을 저장했습니다: {Path(path).name}")

    def _save_session(self) -> None:
        if (
            self.last_input is None
            or self.last_profile is None
            or self.last_result is None
            or self.last_baseline is None
        ):
            messagebox.showinfo("계산 필요", "먼저 계산을 실행해 주세요.", parent=self)
            return
        SESSION_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        payload = {
            "schema_version": 1,
            "recorded_at": timestamp,
            "note": self.note_var.get().strip(),
            "input": asdict(self.last_input),
            "tuning_profile": asdict(self.last_profile),
            "baseline_result": self.last_baseline.to_dict(),
            "result": self.last_result.to_dict(),
        }
        filename = datetime.now().strftime("water-session-%Y%m%d-%H%M%S.json")
        path = filedialog.asksaveasfilename(
            parent=self,
            title="실험 세션 저장",
            initialdir=SESSION_DIR,
            initialfile=filename,
            defaultextension=".json",
            filetypes=(("JSON", "*.json"),),
        )
        if not path:
            return
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.status_var.set(f"실험 세션을 저장했습니다: {Path(path).name}")


def main() -> None:
    app = WaterCalculatorLab()
    app.mainloop()


if __name__ == "__main__":
    main()
