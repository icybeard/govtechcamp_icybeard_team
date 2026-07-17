/**
 * Русские названия районов из латинских shapeName (geoBoundaries ADM2).
 *
 * Границы районов приходят с транслитерированными именами («Mugalzharskiy»,
 * «Egindykol'skiy») — для UI переводим обратной транслитерацией: сначала
 * словарь исключений (города и неоднозначные имена), затем пословная
 * транслитерация с диграфами. Окончание «...skiy» само собой даёт «...ский».
 *
 * Это приближение (не официальный справочник КАТО) — спорные случаи
 * добавляются в OVERRIDES точечно.
 */

const OVERRIDES = {
    aqtobe: 'Актобе',
    almaty: 'Алматы',
    astana: 'Астана',
    shymkent: 'Шымкент',
    arkalyk: 'Аркалык',
    turkistan: 'Туркестан',
    zhezqazghan: 'Жезказган',
    stepnogorsk: 'Степногорск',
    ekibastuz: 'Экибастуз',
    balqash: 'Балхаш',
    temirtau: 'Темиртау',
    kentau: 'Кентау'
};

// Диграфы — до одиночных букв; порядок внутри группы важен (shch раньше sh/ch)
const DIGRAPHS = [
    ['shch', 'щ'],
    ['zh', 'ж'],
    ['kh', 'х'],
    ['ts', 'ц'],
    ['ch', 'ч'],
    ['sh', 'ш'],
    ['yu', 'ю'],
    ['ya', 'я'],
    ['yo', 'ё'],
    ['iy', 'ий'],
    ['ay', 'ай'],
    ['ey', 'ей'],
    ['oy', 'ой'],
    ['uy', 'уй'],
    ['yy', 'ый']
];

const SINGLES = {
    a: 'а', b: 'б', v: 'в', g: 'г', d: 'д', e: 'е', z: 'з', i: 'и', j: 'ж',
    k: 'к', l: 'л', m: 'м', n: 'н', o: 'о', p: 'п', q: 'к', r: 'р', s: 'с',
    t: 'т', u: 'у', f: 'ф', h: 'х', c: 'к', w: 'в', x: 'кс', y: 'ы',
    "'": 'ь', '`': 'ь', 'ʼ': 'ь'
};

function transliterateWord(word) {
    const low = word.toLowerCase();
    if (OVERRIDES[low]) return OVERRIDES[low];
    let out = '';
    let i = 0;
    while (i < low.length) {
        const digraph = DIGRAPHS.find(([latin]) => low.startsWith(latin, i));
        if (digraph) {
            out += digraph[1];
            i += digraph[0].length;
        } else {
            out += SINGLES[low[i]] ?? low[i];
            i += 1;
        }
    }
    return out.charAt(0).toUpperCase() + out.slice(1);
}

/** «Mugalzharskiy» → «Мугалжарский»; уже-кириллические строки возвращаются как есть. */
export function ruDistrictName(name) {
    if (!name || /[а-яА-ЯёЁ]/.test(name)) return name;
    return name
        .split(/(\s+|-)/)
        .map((part) => (/^(\s+|-)$/.test(part) ? part : transliterateWord(part)))
        .join('');
}
