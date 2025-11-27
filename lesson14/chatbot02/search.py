from scipy import spatial  # вычисляет сходство векторов
EMBEDDING_MODEL = "text-embedding-ada-002"

# Функция поиска
def strings_ranked_by_relatedness(
    query: str, # пользовательский запрос
    df: pd.DataFrame, # DataFrame со столбцами text и embedding (база знаний)
    relatedness_fn=lambda x, y: 1 - spatial.distance.cosine(x, y), # функция схожести, косинусное расстояние
    top_n: int = 100 # выбор лучших n-результатов
) -> tuple[list[str], list[float]]: # Функция возвращает кортеж двух списков, первый содержит строки, второй - числа с плавающей запятой
    """Возвращает строки и схожести, отсортированные от большего к меньшему"""

    # Отправляем в OpenAI API пользовательский запрос для токенизации
    query_embedding_response = openai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )

    # Получен токенизированный пользовательский запрос
    query_embedding = query_embedding_response.data[0].embedding

    # Сравниваем пользовательский запрос с каждой токенизированной строкой DataFrame
    strings_and_relatednesses = [
        (row["text"], relatedness_fn(query_embedding, row["embedding"]))
        for i, row in df.iterrows()
    ]

    # Сортируем по убыванию схожести полученный список
    strings_and_relatednesses.sort(key=lambda x: x[1], reverse=True)

    # Преобразовываем наш список в кортеж из списков
    strings, relatednesses = zip(*strings_and_relatednesses)

    # Возвращаем n лучших результатов
    return strings[:top_n], relatednesses[:top_n]