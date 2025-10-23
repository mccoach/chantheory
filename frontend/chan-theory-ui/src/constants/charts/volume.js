// src/constants/charts/volume.js
import { STYLE_PALETTE } from "../common";

// 量窗默认设置
export const DEFAULT_VOL_SETTINGS = {
  mode: "vol",
  unit: "auto",
  rvolN: 20,
  volBar: {
    barPercent: 100,
    upColor: STYLE_PALETTE.bars.volume.up,
    downColor: STYLE_PALETTE.bars.volume.down,
  },
  mavolStyles: {
    MAVOL5: {
      enabled: true, period: 5, width: 1, style: "solid", color: STYLE_PALETTE.lines[0].color, namePrefix: "MAVOL",
    },
    MAVOL10: {
      enabled: true, period: 10, width: 1, style: "solid", color: STYLE_PALETTE.lines[1].color, namePrefix: "MAVOL",
    },
    MAVOL20: {
      enabled: true, period: 20, width: 1, style: "solid", color: STYLE_PALETTE.lines[2].color, namePrefix: "MAVOL",
    },
  },
  markerPump: {
    enabled: true, shape: "triangle", color: "#FFFF00", threshold: 1.5,
  },
  markerDump: {
    enabled: true, shape: "diamond", color: "#00ff00", threshold: 0.7,
  },
};

// 量窗标记尺寸
export const DEFAULT_VOL_MARKER_SIZE = {
  minPx: 1,
  maxPx: 16,
  markerHeightPx: 10,
  markerYOffsetPx: 2,
};
