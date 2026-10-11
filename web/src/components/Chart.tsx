import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { useTheme } from "./theme";

echarts.use([
  BarChart,
  LineChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent,
  AriaComponent,
  SVGRenderer,
]);

/** Значения CSS-токенов для текущей темы (графики не читают CSS-переменные сами). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function chartTokens() {
  return {
    text: cssVar("--text"),
    text2: cssVar("--text-2"),
    text3: cssVar("--text-3"),
    surface: cssVar("--surface"),
    grid: cssVar("--chart-grid"),
    accent: cssVar("--chart-accent"),
    context: cssVar("--chart-context"),
    ref: cssVar("--chart-ref"),
    pos: cssVar("--chart-pos"),
    neg: cssVar("--chart-neg"),
    cat: [1, 2, 3, 4, 5].map((i) => cssVar(`--chart-${i}`)),
    danger: cssVar("--danger"),
  };
}

export type ChartTokens = ReturnType<typeof chartTokens>;

/** Базовые оси и подсказка по dataviz.md: волосяная сетка, оси с единицами, текст цветом текста. */
export function baseOption(t: ChartTokens): EChartsCoreOption {
  return {
    animationDuration: 180,
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: t.text2, fontSize: 12 },
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.grid,
      textStyle: { color: t.text, fontSize: 13 },
      extraCssText: "border-radius:12px;box-shadow:0 4px 16px rgba(20,27,45,.12);",
    },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
  };
}

export function axisCommon(t: ChartTokens) {
  return {
    axisLine: { lineStyle: { color: t.grid } },
    axisTick: { show: false },
    axisLabel: { color: t.text2, fontSize: 12, hideOverlap: true },
    splitLine: { lineStyle: { color: t.grid, width: 1, type: "solid" as const } },
    nameTextStyle: { color: t.text3, fontSize: 12 },
  };
}

export function Chart({
  option,
  height = 280,
  label,
}: {
  option: (t: ChartTokens) => EChartsCoreOption;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  const { theme } = useTheme();
  useEffect(() => {
    if (!ref.current) return;
    inst.current = echarts.init(ref.current, undefined, { renderer: "svg" });
    const ro = new ResizeObserver(() => inst.current?.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      inst.current?.dispose();
    };
  }, []);
  useEffect(() => {
    const t = chartTokens();
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    try {
      inst.current?.setOption(
        { ...baseOption(t), ...option(t), animation: !reduce, aria: { enabled: true, label: { description: label } } },
        true,
      );
    } catch (e) {
      console.warn("График не отрисован", e);
    }
  }, [option, theme, label]);
  return <div ref={ref} style={{ height, width: "100%" }} role="img" aria-label={label} />;
}
