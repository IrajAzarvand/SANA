// ═══════════════════════════════════════════════
// تبدیل شمسی ↔ میلادی — الگوریتم استاندارد
// بدون هیچ وابستگی خارجی
// ═══════════════════════════════════════════════

function div(a, b) { return ~~(a / b); }
function mod(a, b) { return a - ~~(a / b) * b; }

function g2d(gy, gm, gd) {
  let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4)
    + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

function d2g(jdn) {
  let j = 4 * jdn + 139361631;
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

function jalCal(jy) {
  const breaks = [
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178
  ];
  const bl = breaks.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = breaks[0];
  let jm, jump, leap, leapG, march, n, i;

  if (jy < jp || jy >= breaks[bl - 1]) {
    throw new Error('Invalid Jalaali year ' + jy);
  }

  for (i = 1; i < bl; i += 1) {
    jm = breaks[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  n = jy - jp;
  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
  leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  march = 20 + leapJ - leapG;
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
  leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;
  return { leap, gy, march };
}

function j2d(jy, jm, jd) {
  const r = jalCal(jy);
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

function d2j(jdn) {
  const gy = d2g(jdn).gy;
  let jy = gy - 621;
  const r = jalCal(jy);
  const jdn1f = g2d(gy, 3, r.march);
  let jd, jm, k;
  k = jdn - jdn1f;
  if (k >= 0) {
    if (k <= 185) {
      jm = 1 + div(k, 31);
      jd = mod(k, 31) + 1;
      return { jy, jm, jd };
    } else {
      k -= 186;
    }
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  jm = 7 + div(k, 30);
  jd = mod(k, 30) + 1;
  return { jy, jm, jd };
}

// ═══════════════════════════════════════════════
// API عمومی
// ═══════════════════════════════════════════════

export function toJalaaliNum(gy, gm, gd) {
  return d2j(g2d(gy, gm, gd));
}

export function toGregorianNum(jy, jm, jd) {
  return d2g(j2d(jy, jm, jd));
}

export function isLeapJalaliYear(jy) {
  return jalCal(jy).leap === 0;
}

export function getJalaliMonthDays(jy, jm) {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  if (isLeapJalaliYear(jy)) return 30;
  return 29;
}

export function getJalaliMonthName(month) {
  const months = [
    'فروردین', 'اردیبهشت', 'خرداد',
    'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر',
    'دی', 'بهمن', 'اسفند'
  ];
  return months[month - 1] || '';
}

export function toJalali(gregorianDate, separator = '/') {
  if (!gregorianDate) return '';
  try {
    let date;
    if (gregorianDate instanceof Date) date = gregorianDate;
    else date = new Date(gregorianDate);
    if (isNaN(date.getTime())) return '';

    const j = toJalaaliNum(date.getFullYear(), date.getMonth() + 1, date.getDate());
    const jy = j.jy;
    const jm = String(j.jm).padStart(2, '0');
    const jd = String(j.jd).padStart(2, '0');
    return `${jy}${separator}${jm}${separator}${jd}`;
  } catch (e) {
    console.error('Error converting to Jalali:', e, gregorianDate);
    return '';
  }
}

export function toGregorian(jalaliDate) {
  if (!jalaliDate) return '';
  try {
    const parts = jalaliDate.split('/');
    if (parts.length !== 3) return '';
    const jy = parseInt(parts[0]);
    const jm = parseInt(parts[1]);
    const jd = parseInt(parts[2]);
    if (isNaN(jy) || isNaN(jm) || isNaN(jd)) return '';
    const g = toGregorianNum(jy, jm, jd);
    const gy = g.gy;
    const gm = String(g.gm).padStart(2, '0');
    const gd = String(g.gd).padStart(2, '0');
    return `${gy}-${gm}-${gd}`;
  } catch (e) {
    console.error('Error converting to Gregorian:', e, jalaliDate);
    return '';
  }
}

export function todayJalali() {
  const d = new Date();
  const j = toJalaaliNum(d.getFullYear(), d.getMonth() + 1, d.getDate());
  return { jy: j.jy, jm: j.jm, jd: j.jd };
}

export function todayGregorian() {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, '0');
  const d = String(today.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function toPersianDigits(input) {
  if (input === null || input === undefined) return '';
  const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  return String(input).replace(/\d/g, (d) => persianDigits[d]);
}

export const JALALI_WEEKDAYS = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];