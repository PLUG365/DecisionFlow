import { describe, expect, it } from "vitest";
import { calendarDateKey, currentCalendarDateKey } from "./calendar-date";

describe("calendarDateKey", () => {
  it("日付だけの文字列を YYYYMMDD の数値にする", () => {
    expect(calendarDateKey("2026-08-12")).toBe(20260812);
  });

  it("時刻付きでも同じ日なら同じ鍵になる", () => {
    expect(calendarDateKey("2026-08-12T00:00:00Z")).toBe(20260812);
    expect(calendarDateKey("2026-08-12T23:59:59Z")).toBe(20260812);
    expect(calendarDateKey("2026-08-12T09:30:00+09:00")).toBe(20260812);
  });

  it("空・null・undefined は鍵を持たない", () => {
    expect(calendarDateKey(null)).toBeNull();
    expect(calendarDateKey(undefined)).toBeNull();
    expect(calendarDateKey("")).toBeNull();
  });

  it("形が違う文字列は弾く", () => {
    expect(calendarDateKey("2026/08/12")).toBeNull();
    expect(calendarDateKey("12-08-2026")).toBeNull();
    expect(calendarDateKey("not a date")).toBeNull();
  });

  /** 形は正しいが存在しない日。Date が繰り上げるので明示的に弾く。 */
  it("存在しない日付は弾く", () => {
    expect(calendarDateKey("2026-02-30")).toBeNull();
    expect(calendarDateKey("2026-13-01")).toBeNull();
    expect(calendarDateKey("2025-02-29")).toBeNull();
  });

  it("うるう日は通す", () => {
    expect(calendarDateKey("2028-02-29")).toBe(20280229);
  });

  it("鍵は日付順に単調で、月や年をまたいでも比較できる", () => {
    const keys = [
      calendarDateKey("2025-12-31"),
      calendarDateKey("2026-01-01"),
      calendarDateKey("2026-01-31"),
      calendarDateKey("2026-02-01"),
    ] as number[];
    expect(keys).toEqual([...keys].sort((a, b) => a - b));
  });
});

describe("currentCalendarDateKey", () => {
  it("ローカル時刻の今日を同じ形で返す", () => {
    expect(currentCalendarDateKey(new Date(2026, 7, 12, 13, 45))).toBe(
      20260812,
    );
  });

  it("同じ日なら時刻が違っても同値で、期限当日を過ぎたことにしない", () => {
    const morning = currentCalendarDateKey(new Date(2026, 7, 12, 0, 0));
    const night = currentCalendarDateKey(new Date(2026, 7, 12, 23, 59));
    expect(morning).toBe(night);
    expect(calendarDateKey("2026-08-12")).toBe(night);
  });
});
