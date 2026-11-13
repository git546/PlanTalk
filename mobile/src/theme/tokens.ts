export const colors = {
  canvas: '#F3F6F2',
  surface: '#FFFFFF',
  surfaceMuted: '#F7F9F6',
  surfaceBrand: '#E7F1E9',
  brand: '#236B47',
  brandStrong: '#174C33',
  brandSoft: '#D6E8DB',
  text: '#172B20',
  textSecondary: '#526158',
  textMuted: '#758179',
  border: '#DCE4DE',
  borderStrong: '#BFCFC4',
  warningSurface: '#FFF4DC',
  warningText: '#6D4A14',
  dangerSurface: '#FDECEA',
  danger: '#A6382C',
  disabled: '#A9B5AD',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
} as const;

export const layout = {
  maxContentWidth: 480,
  pagePadding: 16,
  minimumTapTarget: 44,
} as const;
