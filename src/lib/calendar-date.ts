/**
 * 「暦の上の日付」だけを比べるための鍵。時刻とタイムゾーンを落として `YYYYMMDD` の
 * 数値にする。期限超過の判定は**時刻を見ない**（希望期限は日付で運用されており、
 * 同じ日なら何時でも「当日」でなければならない）。
 *
 * **判断キューとダッシュボードが同じ関数を使う。** 以前はこの関数と
 * `currentCalendarDateKey` が `queue-priority.ts` と `dashboard-actions.ts` へ
 * 正規表現ごと2重定義されていて、片方だけが `null | undefined` を受けるよう
 * 育っていた。同じ規則が2箇所にあると、両方のテストが緑のまま食い違える。
 */
export function calendarDateKey(
  value: string | null | undefined,
): number | null {
  if (!value) return null;
  const match =
    /^(\d{4})-(\d{2})-(\d{2})(?:T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)?)?$/.exec(
      value,
    );
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  // 2026-02-30 のような「形は正しいが存在しない日」を弾く。
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  return year * 10000 + month * 100 + day;
}

/** 実行時の「今日」を同じ鍵の形で返す。ローカル時刻で見る。 */
export function currentCalendarDateKey(now: Date): number {
  return (
    now.getFullYear() * 10000 + (now.getMonth() + 1) * 100 + now.getDate()
  );
}

/**
 * 経過時間を「日」で数えるための長さ。**上の暦日の鍵とは別の用途**で、
 * 「最後の活動から何日経ったか」「下書きの保持期限を過ぎたか」に使う。
 * 暦をまたいだかどうかを見たいときは `calendarDateKey` の比較を使うこと。
 */
export const DAY_IN_MS = 24 * 60 * 60 * 1000;
