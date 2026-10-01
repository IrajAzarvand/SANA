/**
 * اعداد نمایشی رابط کاربری را به رقم فارسی تبدیل می‌کند.
 *
 * متن ورودی/فرم‌ها دست‌نخورده می‌مانند؛ فقط Text Nodeهای قابل مشاهده
 * در رابط کاربری تبدیل می‌شوند تا شناسه‌های فنی و مقدار inputها قابل کپی
 * و ارسال به API باقی بمانند.
 */
const LATIN_DIGITS = /[0-9]/g;
const PERSIAN_DIGITS = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹'];

export function toPersianDigits(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(LATIN_DIGITS, (digit) => PERSIAN_DIGITS[digit]);
}

function shouldSkipTextNode(node) {
  const parent = node.parentElement;
  if (!parent) return true;

  const tag = parent.tagName.toLowerCase();
  if (['script', 'style', 'textarea', 'input', 'select', 'option'].includes(tag)) return true;
  if (parent.isContentEditable) return true;
  if (parent.closest('[data-latin-digits="true"]')) return true;

  return false;
}

function convertTextNode(node) {
  if (shouldSkipTextNode(node)) return;
  if (!LATIN_DIGITS.test(node.nodeValue || '')) {
    LATIN_DIGITS.lastIndex = 0;
    return;
  }

  LATIN_DIGITS.lastIndex = 0;
  const converted = toPersianDigits(node.nodeValue);
  if (converted !== node.nodeValue) {
    node.nodeValue = converted;
  }
}

/**
 * فعال‌سازی تبدیل سراسری اعداد نمایشی.
 * MutationObserver باعث می‌شود متن‌های داینامیک React نیز پوشش داده شوند.
 */
export function installPersianDigitsObserver(root = document.body) {
  if (!root || root.dataset.persianDigitsObserver === 'true') return () => {};

  root.dataset.persianDigitsObserver = 'true';

  const scan = (container) => {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let node = walker.nextNode();
    while (node) {
      nodes.push(node);
      node = walker.nextNode();
    }
    nodes.forEach(convertTextNode);
  };

  scan(root);

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'characterData') {
        convertTextNode(mutation.target);
        continue;
      }

      mutation.addedNodes.forEach((addedNode) => {
        if (addedNode.nodeType === Node.TEXT_NODE) {
          convertTextNode(addedNode);
        } else if (addedNode.nodeType === Node.ELEMENT_NODE) {
          scan(addedNode);
        }
      });
    }
  });

  observer.observe(root, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  return () => {
    observer.disconnect();
    delete root.dataset.persianDigitsObserver;
  };
}
