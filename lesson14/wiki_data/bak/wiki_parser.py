# Отключим предупреждения в колабе. Будет меньше лишней информации в выводе
import warnings
warnings.filterwarnings('ignore')

# imports
import mwclient  # библиотека для работы с MediaWiki API для загрузки примеров статей Википедии
import mwparserfromhell  # Парсер для MediaWiki
import openai  # будем использовать для токинизации
import pandas as pd  # В DataFrame будем хранить базу знаний и результат токинизации базы знаний
import re  # для вырезания ссылок <ref> из статей Википедии
import tiktoken  # для подсчета токенов
import time

# Токен бота (тот, что вы получили в BotFather)
BOT_API_KEY='8379543592:AAHuDc0GQjd9qsew3nTO08gnbgFHHt-6_2c'
OPENAI_API_KEY='sk-or-vv-0b6b31bb4c466a250b23192b76642e66f17692d317071356b39716069f5ee744'
base_url="https://api.vsegpt.ru/v1"
model='openai/gpt-5-nano'
GPT_MODEL='gpt-5-nano'
embedding_model='emb-openai/text-embedding-3-small'

# Задаем категорию и англоязычную версию Википедии для поиска
CATEGORY_TITLE = "Category:2022 Winter Olympics"
WIKI_SITE = "en.wikipedia.org"
PAUSE = 0.1   # 100 мс между запросами


# Уровень логирования: INFO в обычной работе, DEBUG — для отладки
LOG_LEVEL='INFO'

# Соберем заголовки всех статей
def titles_from_category(
    category: mwclient.listing.Category, # Задаем типизированный параметр категории статей
    max_depth: int # Определяем глубину вложения статей
) -> set[str]:
    """Возвращает набор заголовков страниц в данной категории Википедии и ее подкатегориях."""
    titles = set() # Используем множество для хранения заголовков статей
    for cm in category.members(): # Перебираем вложенные объекты категории
        time.sleep(PAUSE)
        if type(cm) == mwclient.page.Page: # Если объект является страницей
            titles.add(cm.name) # в хранилище заголовков добавляем имя страницы
        elif isinstance(cm, mwclient.listing.Category) and max_depth > 0: # Если объект является категорией и глубина вложения не достигла максимальной
            deeper_titles = titles_from_category(cm, max_depth=max_depth - 1) # вызываем рекурсивно функцию для подкатегории
            titles.update(deeper_titles) # добавление в множество элементов из другого множества
    return titles

# Инициализация объекта MediaWiki
# WIKI_SITE ссылается на англоязычную часть Википедии
site = mwclient.Site(WIKI_SITE)

# Загрузка раздела заданной категории
category_page = site.pages[CATEGORY_TITLE]
# Получение множества всех заголовков категории с вложенностью на один уровень
titles = titles_from_category(category_page, max_depth=1)


print(f"Создано {len(titles)} заголовков статей в категории {CATEGORY_TITLE}.")

# Функция возвращает список всех вложенных секций для заданной секции страницы Википедии
import mwparserfromhell
def all_subsections_from_section(
    section: mwparserfromhell.wikicode.Wikicode, # текущая секция
    parent_titles: list[str], # Заголовки родителя
    sections_to_ignore: set[str], # Секции, которые необходимо проигнорировать
) -> list[tuple[list[str], str]]:
    """
    Из раздела Википедии возвращает список всех вложенных секций.
    Каждый подраздел представляет собой кортеж, где:
      - первый элемент представляет собой список родительских секций, начиная с заголовка страницы
      - второй элемент представляет собой текст секции
    """

    # Извлекаем заголовки текущей секции
    headings = [str(h) for h in section.filter_headings()]
    title = headings[0]
    # Заголовки Википедии имеют вид: "== Heading =="

    if title.strip("=" + " ") in sections_to_ignore:
        # Если заголовок секции в списке для игнора, то пропускаем его
        return []

    # Объединим заголовки и подзаголовки, чтобы сохранить контекст для chatGPT
    titles = parent_titles + [title]

    # Преобразуем wikicode секции в строку
    full_text = str(section)

    # Выделяем текст секции без заголовка
    section_text = full_text.split(title)[1]
    if len(headings) == 1:
        # Если один заголовок, то формируем результирующий список
        return [(titles, section_text)]
    else:
        first_subtitle = headings[1]
        section_text = section_text.split(first_subtitle)[0]
        # Формируем результирующий список из текста до первого подзаголовка
        results = [(titles, section_text)]
        for subsection in section.get_sections(levels=[len(titles) + 1]):
            results.extend(
                # Вызываем функцию получения вложенных секций для заданной секции
                all_subsections_from_section(subsection, titles, sections_to_ignore)
                )  # Объединяем результирующие списки данной функции и вызываемой
        return results

# Функция возвращает список всех секций страницы, за исключением тех, которые отбрасываем
def all_subsections_from_title(
    title: str, # Заголовок статьи Википедии, которую парсим
    sections_to_ignore: set[str] = SECTIONS_TO_IGNORE, # Секции, которые игнорируем
    site_name: str = WIKI_SITE, # Ссылка на сайт википедии
) -> list[tuple[list[str], str]]:
    """
    Из заголовка страницы Википедии возвращает список всех вложенных секций.
    Каждый подраздел представляет собой кортеж, где:
      - первый элемент представляет собой список родительских секций, начиная с заголовка страницы
      - второй элемент представляет собой текст секции
    """

    # Инициализация объекта MediaWiki
    # WIKI_SITE ссылается на англоязычную часть Википедии
    site = mwclient.Site(site_name)

    # Запрашиваем страницу по заголовку
    page = site.pages[title]

    # Получаем текстовое представление страницы
    text = page.text()

    # Удобный парсер для MediaWiki
    parsed_text = mwparserfromhell.parse(text)
    # Извлекаем заголовки
    headings = [str(h) for h in parsed_text.filter_headings()]
    if headings: # Если заголовки найдены
        # В качестве резюме берем текст до первого заголовка
        summary_text = str(parsed_text).split(headings[0])[0]
    else:
        # Если нет заголовков, то весь текст считаем резюме
        summary_text = str(parsed_text)
    results = [([title], summary_text)] # Добавляем резюме в результирующий список
    for subsection in parsed_text.get_sections(levels=[2]): # Извлекаем секции 2-го уровня
        results.extend(
            # Вызываем функцию получения вложенных секций для заданной секции
            all_subsections_from_section(subsection, [title], sections_to_ignore)
        ) # Объединяем результирующие списки данной функции и вызываемой
    return results

# Разбивка статей на секции
# придется немного подождать, так как на парсинг 100 статей требуется около минуты
wikipedia_sections = []
for title in titles:
    wikipedia_sections.extend(all_subsections_from_title(title))
print(f"Найдено {len(wikipedia_sections)} секций на {len(titles)} страницах")

# Очистка текста секции от ссылок <ref>xyz</ref>, начальных и конечных пробелов
def clean_section(section: tuple[list[str], str]) -> tuple[list[str], str]:
    titles, text = section
    # Удаляем ссылки
    text = re.sub(r"<ref.*?</ref>", "", text)
    # Удаляем пробелы вначале и конце
    text = text.strip()
    return (titles, text)

# Применим функцию очистки ко всем секциям с помощью генератора списков
wikipedia_sections = [clean_section(ws) for ws in wikipedia_sections]

# Отфильтруем короткие и пустые секции
def keep_section(section: tuple[list[str], str]) -> bool:
    """Возвращает значение True, если раздел должен быть сохранен, в противном случае значение False."""
    titles, text = section
    # Фильтруем по произвольной длине, можно выбрать и другое значение
    if len(text) < 16:
        return False
    else:
        return True


original_num_sections = len(wikipedia_sections)
wikipedia_sections = [ws for ws in wikipedia_sections if keep_section(ws)]
print(f"Отфильтровано {original_num_sections-len(wikipedia_sections)} секций, осталось {len(wikipedia_sections)} секций.")

# Функция подсчета токенов
def num_tokens(text: str, model: str = GPT_MODEL) -> int:
    """Возвращает число токенов в строке."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Функция разделения строк
def halved_by_delimiter(string: str, delimiter: str = "\n") -> list[str, str]:
    """Разделяет строку надвое с помощью разделителя (delimiter), пытаясь сбалансировать токены с каждой стороны."""

    # Делим строку на части по разделителю, по умолчанию \n - перенос строки
    chunks = string.split(delimiter)
    if len(chunks) == 1:
        return [string, ""]  # разделитель не найден
    elif len(chunks) == 2:
        return chunks  # нет необходимости искать промежуточную точку
    else:
        # Считаем токены
        total_tokens = num_tokens(string)
        halfway = total_tokens // 2
        # Предварительное разделение по середине числа токенов
        best_diff = halfway
        # В цикле ищем какой из разделителей, будет ближе всего к best_diff
        for i, chunk in enumerate(chunks):
            left = delimiter.join(chunks[: i + 1])
            left_tokens = num_tokens(left)
            diff = abs(halfway - left_tokens)
            if diff >= best_diff:
                break
            else:
                best_diff = diff
        left = delimiter.join(chunks[:i])
        right = delimiter.join(chunks[i:])
        # Возвращаем левую и правую часть оптимально разделенной строки
        return [left, right]


# Функция обрезает строку до максимально разрешенного числа токенов
def truncated_string(
    string: str, # строка
    model: str, # модель
    max_tokens: int, # максимальное число разрешенных токенов
    print_warning: bool = True, # флаг вывода предупреждения
) -> str:
    """Обрезка строки до максимально разрешенного числа токенов."""
    encoding = tiktoken.encoding_for_model(model)
    encoded_string = encoding.encode(string)
    # Обрезаем строку и декодируем обратно
    truncated_string = encoding.decode(encoded_string[:max_tokens])
    if print_warning and len(encoded_string) > max_tokens:
        print(f"Предупреждение: Строка обрезана с {len(encoded_string)} токенов до {max_tokens} токенов.")
    # Усеченная строка
    return truncated_string

# Функция делит секции статьи на части по максимальному числу токенов
def split_strings_from_subsection(
    subsection: tuple[list[str], str], # секции
    max_tokens: int = 1000, # максимальное число токенов
    model: str = GPT_MODEL, # модель
    max_recursion: int = 5, # максимальное число рекурсий
) -> list[str]:
    """
    Разделяет секции на список из частей секций, в каждой части не более max_tokens.
    Каждая часть представляет собой кортеж родительских заголовков [H1, H2, ...] и текста (str).
    """
    titles, text = subsection
    string = "\n\n".join(titles + [text])
    num_tokens_in_string = num_tokens(string)
    # Если длина соответствует допустимой, то вернет строку
    if num_tokens_in_string <= max_tokens:
        return [string]
    # если в результате рекурсия не удалось разделить строку, то просто усечем ее по числу токенов
    elif max_recursion == 0:
        return [truncated_string(string, model=model, max_tokens=max_tokens)]
    # иначе разделим пополам и выполним рекурсию
    else:
        titles, text = subsection
        for delimiter in ["\n\n", "\n", ". "]: # Пробуем использовать разделители от большего к меньшему (разрыв, абзац, точка)
            left, right = halved_by_delimiter(text, delimiter=delimiter)
            if left == "" or right == "":
                # если какая-либо половина пуста, повторяем попытку с более простым разделителем
                continue
            else:
                # применим рекурсию на каждой половине
                results = []
                for half in [left, right]:
                    half_subsection = (titles, half)
                    half_strings = split_strings_from_subsection(
                        half_subsection,
                        max_tokens=max_tokens,
                        model=model,
                        max_recursion=max_recursion - 1, # уменьшаем максимальное число рекурсий
                    )
                    results.extend(half_strings)
                return results
    # иначе никакого разделения найдено не было, поэтому просто обрезаем строку (должно быть очень редко)
    return [truncated_string(string, model=model, max_tokens=max_tokens)]

# Делим секции на части
MAX_TOKENS = 1600
wikipedia_strings = []
for section in wikipedia_sections:
    wikipedia_strings.extend(split_strings_from_subsection(section, max_tokens=MAX_TOKENS))

print(f"{len(wikipedia_sections)} секций Википедии поделены на {len(wikipedia_strings)} строк.")  

from openai import OpenAI

# Инициализация клиента под провайдера VseGPT
client = OpenAI(
    api_key="OPENAI_API_KEY",             # ваш ключ VseGPT
    base_url="https://api.vsegpt.ru/v1",
)

# Универсальная функция получения эмбеддинга через VseGPT
def get_embedding(text, model=embedding_model):
    response = client.embeddings.create(
        model=model,
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

df = pd.DataFrame({"text": wikipedia_strings[:10]})

df['embedding'] = df.text.apply(lambda x: get_embedding(x, model='text-embedding-ada-002'))

SAVE_PATH = "./winter_olympics_2022.csv"
# Сохранение результата
df.to_csv(SAVE_PATH, index=False)