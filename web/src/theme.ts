// Theme tokens shared by CSS and Plotly. Chart colours follow the validated reference palette:
// categorical slots 1-3, one-hue sequential ramps (re-stepped for dark), blue<->red diverging.
import { createContext, useContext } from "react";

export type ThemeName = "light" | "dark";

export interface ChartTheme {
  name: ThemeName;
  text: string;
  muted: string;
  grid: string;
  surface: string;
  outline: string;
  selected: string;
  series: string[];
  band: string;
  seqBlue: string[];
  seqOrange: string[];
  diverging: string[];
  up: string;
  down: string;
  total: string;
}

const light: ChartTheme = {
  name: "light",
  text: "#0b0b0b",
  muted: "#52514e",
  grid: "rgba(82,81,78,0.14)",
  surface: "#fcfcfb",
  outline: "rgba(252,252,251,0.95)",
  selected: "#0b0b0b",
  series: ["#2a78d6", "#eb6834", "#1baf7a"],
  band: "rgba(42,120,214,0.16)",
  seqBlue: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  seqOrange: ["#fde3d6", "#f9c1a6", "#f49a74", "#eb6834", "#c94f1f", "#9c3b15", "#6e290e"],
  diverging: ["#184f95", "#6da7ec", "#f0efec", "#f08a89", "#b8302f"],
  up: "#e34948",
  down: "#2a78d6",
  total: "#52514e",
};

const dark: ChartTheme = {
  name: "dark",
  text: "#ffffff",
  muted: "#c3c2b7",
  grid: "rgba(195,194,183,0.14)",
  surface: "#1a1a19",
  outline: "rgba(26,26,25,0.95)",
  selected: "#ffffff",
  series: ["#3987e5", "#d95926", "#199e70"],
  band: "rgba(57,135,229,0.22)",
  // In dark mode low values recede toward the dark surface and high values glow
  seqBlue: ["#104281", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
  seqOrange: ["#6e290e", "#9c3b15", "#c94f1f", "#d95926", "#f49a74", "#f9c1a6", "#fde3d6"],
  diverging: ["#3987e5", "#1c5cab", "#383835", "#a33a39", "#e66767"],
  up: "#e66767",
  down: "#3987e5",
  total: "#8a8983",
};

export const THEMES = { light, dark };
export const ThemeContext = createContext<ChartTheme>(light);
export const useChartTheme = () => useContext(ThemeContext);

export function scale(colors: string[]): [number, string][] {
  return colors.map((c, i) => [i / (colors.length - 1), c]);
}
