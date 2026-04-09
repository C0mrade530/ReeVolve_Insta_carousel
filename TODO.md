# TODO — Универсальная Мульти-Нишевая Платформа + Виральность

> Выполняй задачи СТРОГО ПОЭТАПНО (1 → 2 → 3...). После каждого файла — `py_compile.compile()`.
> Не меняй CometAPI конфигурацию. НЕ трогай publisher/, parser/, competitor/.
> Код и комментарии — английский. Интерфейс — русский.

---

## ЗАДАЧА 1: Создать систему ниш — `backend/app/utils/niche_configs.py`

**Новый файл.** Это фундамент — словарь конфигураций для каждой ниши.

Создай файл `backend/app/utils/niche_configs.py` с 6 нишами. Каждая ниша — dict с этими полями:

```python
{
    "display_name": str,         # "Недвижимость", "AI & Технологии" и т.д.
    "category": str,             # "premium" (недвиж) или "universal"
    "role": str,                 # "риелтор", "AI-эксперт", "психолог", "предприниматель", "тренер", "эксперт"
    "target_audience": str,      # 2-3 предложения описание ЦА
    "pain_triggers": list[str],  # 6-12 триггеров боли с примерами
    "viral_formulas": list[str], # 8-14 виральных формул с примерами заголовков
    "voice_tone": str,           # описание голоса/тона автора
    "example_hooks": list[str],  # 3-4 примера заголовков с КАПС и скобками
    "slide_examples": dict,      # примеры текстов для pain/more_pain/hope/solution/philosophical
    "evaluation_criteria": dict, # 10 критериев оценки {НАЗВАНИЕ: описание}
    "red_flags": list[str],      # 5-7 красных флагов
    "banned_phrases": list[str], # 15-20 запрещённых AI-фраз
    "hashtag_count": str,        # "5-7"
    "default_template": str,     # ID шаблона дизайна
    "default_font": str,         # ID шрифтовой пары
}
```

### Ниша "недвижимость" (Премиум)
- category: "premium"
- role: "риелтор"
- 12 pain_triggers (страх ипотеки, нехватка на первоначалку, обман застройщиков, страх продешевить, аренда как ловушка, развод и раздел, инвестиции в бетон, переезд, новостройка vs вторичка, маткапитал, ставка ЦБ, скрытые расходы)
- 14 viral_formulas (шок-история, разоблачение мифа, инверсия, секреты изнутри, сравнение-удар, личная история, список ошибок, контроверсия, инсайдерская инфо, кейс с цифрами, срочность, до/после, калькулятор, диалог с банком)
- voice_tone: "опытный риелтор, который видел сотни сделок. Рассказывает реальные истории клиентов с именами, суммами, деталями. Говорит просто, на 'ты', как друг за кофе."
- 4 example_hooks из текущих промптов
- slide_examples: Марина/аренда история (из текущего SLIDES_WRITER_SYSTEM)
- 10 evaluation_criteria: HOOK, STORY, PAIN, EXPERTISE, CONCRETE, SCROLL, SAVE, CAPTION, SHARE, SLIDE2_HOOK
- default_template: "expert", default_font: "luxury"

### Ниша "ai_blog" (AI & Технологии)
- role: "AI-эксперт"
- target_audience: "Люди 20-45 лет: хотят использовать AI для работы и бизнеса, боятся отстать от технологий, не понимают как начать, тонут в информационном шуме, хотят автоматизировать рутину."
- 8 pain_triggers: страх замены AI, информационный перегруз, неумение промптить, потеря денег на курсах, сложность инструментов, страх отстать, не понимают что реально а что хайп, не знают с чего начать
- 10 viral_formulas: миф про AI и правда, кейс "я использовал AI и вот что вышло", AI vs человек, секреты промптинга, скрытые фичи инструмента, "потратил 30 часов чтобы вы не тратили", предсказание будущего AI, разоблачение AI-курсов, калькулятор экономии времени, "ЭТО заменит ваш текущий инструмент"
- voice_tone: "любопытный технолог, который пробует всё на себе. Объясняет сложное простыми словами. Даёт конкретные инструменты и промпты. Честен про ограничения AI."
- 4 example_hooks про AI с КАПС и скобками
- slide_examples: история использования AI для конкретной задачи
- 10 criteria: HOOK, CLARITY, PRACTICAL, ACCURACY, PERSPECTIVE, SAVE, LEARNING, ENGAGEMENT, SHARE, SLIDE2_HOOK
- default_template: "vibrant", default_font: "modern_clean"

### Ниша "psychology" (Психология, мотивация, отношения, философия)
- role: "психолог"
- target_audience: "Люди 18-55 лет: проблемы с самооценкой, тревожность, токсичные отношения, прокрастинация, выгорание, поиск смысла, страх перемен, созависимость."
- 10 pain_triggers: токсичные отношения, низкая самооценка, страх одиночества, выгорание, прокрастинация, созависимость, страх перемен, неумение говорить "нет", чувство пустоты, сравнение с другими
- 10 viral_formulas: психологический парадокс, история исцеления, опасное убеждение большинства, техника за 5 минут, "когда я понял ЭТО", разоблачение токсичных привычек, мудрость через боль, "ваш страх говорит о...", "это НЕ ваша вина", неожиданная причина проблемы
- voice_tone: "уважительный психолог, открытый и уязвимый. Примеры из практики (с согласия клиентов). Без нравоучений. Научная база + человечность."
- 4 example_hooks: эмоциональные, про отношения, самооценку, страхи
- slide_examples: история клиента с трансформацией
- 10 criteria: HOOK, INSIGHT, EMPATHY, EVIDENCE, ACTIONABLE, SAFETY, CREDIBILITY, ENGAGEMENT, SHARE, SLIDE2_HOOK
- red_flags: переупрощение, нет оговорки о профпомощи, "психопоп" стиль, мнение как факт
- default_template: "warm", default_font: "elegant_serif"

### Ниша "business" (Бизнес, предпринимательство)
- role: "предприниматель"
- target_audience: "Люди 25-50 лет: хотят запустить или масштабировать бизнес, увеличить доход, уйти с найма, избежать ошибок, найти клиентов."
- 8 pain_triggers: страх вложений, нет клиентов, выгорание, конкуренция, зависимость от одного клиента, нехватка денег на старте, неправильная стратегия, проблемы с делегированием
- 10 viral_formulas: ошибка за 500к, история провала и восстановления, формула первых 100к, секрет масштабирования, "закрыл бизнес и открыл заново", ошибки найма, "один клиент принёс 80% выручки", скрытые расходы бизнеса, "что я сделал бы иначе", 3 пути к первому миллиону
- voice_tone: "опытный предприниматель, честный про свои ошибки. Конкретные цифры выручки, расходов, маржи. Не коуч, а практик."
- default_template: "professional", default_font: "business_pro"

### Ниша "fitness" (Фитнес, здоровье, питание)
- role: "тренер"
- target_audience: "Люди 20-50 лет: хотят похудеть, набрать форму, улучшить здоровье, устали от диет, не знают с чего начать, боятся травм."
- 8 pain_triggers: страх диет и ограничений, нехватка мотивации, травмы и боль, неправильная техника, трата денег без результата, плато, стыд за своё тело, нет времени на тренировки
- 8 viral_formulas: до/после трансформация, разоблачение мифа о фитнесе, простой лайфхак питания, история борьбы и победы, ошибки новичков, "этот продукт вы считаете полезным (а зря)", "одно упражнение заменяет час в зале", формула калорий
- voice_tone: "мотивирующий тренер, доступный язык, личная история трансформации. Кг, см, недели — конкретика."
- default_template: "vibrant", default_font: "bold_impact"

### Ниша "universal" (Общая — fallback для любой темы)
- role: "эксперт"
- target_audience: "Широкая аудитория, интересующаяся данной темой."
- 5 generic pain_triggers
- 5 generic viral_formulas
- voice_tone: "эксперт с практическим опытом. Доступный язык, конкретные примеры."
- default_template: "clean", default_font: "modern_clean"

**Добавить функции:**
```python
def get_niche_config(niche: str) -> dict:
    """Get niche config with fallback to 'universal'. Case-insensitive partial match."""
    if niche in NICHE_CONFIGS:
        return NICHE_CONFIGS[niche]
    niche_lower = niche.lower()
    for key, cfg in NICHE_CONFIGS.items():
        if niche_lower in cfg.get("display_name", "").lower() or niche_lower in key:
            return cfg
    return NICHE_CONFIGS["universal"]

def get_available_niches() -> list[dict]:
    """Return list of available niches for API/frontend."""
    return [
        {"id": k, "name": v["display_name"], "category": v.get("category", "universal"),
         "role": v["role"], "default_template": v["default_template"]}
        for k, v in NICHE_CONFIGS.items()
    ]
```

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/utils/niche_configs.py')"`

---

## ЗАДАЧА 2: Промпт-фабрики + виральность — `backend/app/utils/prompts.py`

**ВАЖНО:** TOPIC_STRATEGIST_SYSTEM и TOPIC_STRATEGIST_USER уже обновлены (v2.1). Нужно:

### 2a. Обновить SLIDES_WRITER_SYSTEM

Изменения (не заменяй весь промпт, обнови конкретные секции):

1. Правило 5 в "ПРАВИЛА ОПИСАНИЯ (caption)" → CTA на ШЕРЫ:
   - Было: `"5. Призыв к действию (подпишись/напиши в директ/сохрани)"`
   - Стало: `"5. Призыв к ПЕРЕСЫЛКЕ и СОХРАНЕНИЮ: 'Отправь другу, который ищет квартиру', 'Сохрани, пригодится', 'Скинь тому, кто снимает жильё'"`

2. Хэштеги:
   - Было: `"6. 12-15 хэштегов"`
   - Стало: `"6. 5-7 высокорелевантных хэштегов (город + ниша + боль). НЕ спамь 15 штук."`

3. Добавить правило в "ПРАВИЛА ОПИСАНИЯ":
   - `"- ПЕРВОЕ предложение описания содержит ключевое слово (SEO для Instagram Search)"`
   - `"- Финальный CTA направлен на ОТПРАВКУ другу, а не только подписку"`

4. Добавить в "ПРАВИЛА СЛАЙДОВ":
   - `"- СЛАЙД 2 должен цеплять САМОСТОЯТЕЛЬНО — Instagram часто показывает его первым в ленте"`

5. Расширить ЗАПРЕЩЁННЫЕ ФРАЗЫ:
   - Добавить: `"хочу поделиться", "давайте разберёмся", "друзья", "в этом посте", "сегодня поговорим"`

### 2b. Обновить VIRAL_ANALYST_SYSTEM

Добавить 2 критерия (было 8, стало 10):
```
9. SHARE — Отправят другу в директ? Есть конкретный триггер пересылки ("скинь тому, кто...")?
10. SLIDE2_HOOK — Слайд 2 цепляет САМОСТОЯТЕЛЬНО? Если Instagram покажет его первым — кликнут?
```

Добавить 2 красных флага:
```
- CTA только на "подпишись" без триггера пересылки (-3)
- Слайд 2 не понятен без слайда 1 (-3)
```

### 2c. Обновить VIRAL_ANALYST_USER

Обновить пример JSON в scores: добавить `"share": 7, "slide2_hook": 7`.
avg_score теперь считается из 10 критериев.

### 2d. Обновить REFINE_SYSTEM_PROMPT

Добавить правило: `"- CTA направлен на ОТПРАВКУ другу, не только подписку"`
Добавить: `"- Слайд 2 цепляет САМОСТОЯТЕЛЬНО (Instagram показывает его первым)"`

### 2e. Добавить промпт-фабрики (В КОНЕЦ файла, после backward compat aliases)

4 функции:
- `get_topic_strategist_system(niche_config: dict) -> str`
- `get_slides_writer_system(niche_config: dict) -> str`
- `get_viral_analyst_system(niche_config: dict) -> str`
- `get_refine_system(niche_config: dict) -> str`

Каждая функция берёт базовый промпт (TOPIC_STRATEGIST_SYSTEM и т.д.) и заменяет нишевые секции из niche_config. ВАЖНО: каждый replace должен быть обёрнут в `if old_text in base:` чтобы не ломаться если текст не найден.

Ключевые замены в каждой фабрике:
- "для риелторов" → f"для {niche_config['display_name']}"
- "от лица РИЕЛТОРА" → f"от лица {niche_config['role'].upper()}"
- Секция ЦЕЛЕВАЯ АУДИТОРИЯ → niche_config["target_audience"]
- Секция ТРИГГЕРЫ БОЛИ → niche_config["pain_triggers"] (пронумерованный список)
- Секция VIRAL ФОРМУЛЫ → niche_config["viral_formulas"]
- Голос/тон → niche_config["voice_tone"]
- Примеры заголовков → niche_config["example_hooks"]
- Критерии оценки → niche_config["evaluation_criteria"]
- Красные флаги → niche_config["red_flags"]
- Запрещённые фразы → niche_config["banned_phrases"]

Также добавить 2 вспомогательные функции:
```python
def _build_numbered_list(items: list[str]) -> str:
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

def _build_criteria_section(criteria: dict[str, str]) -> str:
    return "\n".join(f"{i+1}. {k} — {v}" for i, (k, v) in enumerate(criteria.items()))
```

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/utils/prompts.py')"`

---

## ЗАДАЧА 3: Обновить content.py — niche_config + thinking budget

1. Добавить импорт: `from app.utils.niche_configs import get_niche_config`
2. Добавить импорт фабрик: `from app.utils.prompts import get_topic_strategist_system, get_slides_writer_system, get_viral_analyst_system, get_refine_system`
3. Поднять `budget_tokens` с 2048 → 4096 (строка ~83)
4. Добавить `niche_config: dict | None = None` и `top_posts_context: str = ""` параметры в `_step1_topic`, `_step2_slides`, `_step3_evaluate`, `_refine_carousel`, `generate_topic_content`
5. В каждой функции: `if not niche_config: niche_config = get_niche_config(niche)`
6. Заменить прямое использование промптов на фабрики:
   - `TOPIC_STRATEGIST_SYSTEM` → `get_topic_strategist_system(niche_config)`
   - `SLIDES_WRITER_SYSTEM` → `get_slides_writer_system(niche_config)`
   - `VIRAL_ANALYST_SYSTEM` → `get_viral_analyst_system(niche_config)`
   - `REFINE_SYSTEM_PROMPT` → `get_refine_system(niche_config)`

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/services/generator/content.py')"`

---

## ЗАДАЧА 4: Добавить 6 дизайн-шаблонов — image.py

1. Заменить единственный `TMPL` dict на `DESIGN_TEMPLATES` с 6 шаблонами (expert, clean, vibrant, warm, professional, creative). Цвета:
   - expert: bg #080808, text white, accent gold #d4a853
   - clean: bg #f5f5f5, text #1a1a1a, accent blue #2563eb
   - vibrant: bg #1a1a2e, text white, accent pink #ff006e
   - warm: bg #fff8f0, text #2d1810, accent orange #ff8c42
   - professional: bg #1f2937, text #f3f4f6, accent green #10b981
   - creative: bg #f0e5ff, text #3f0f5c, accent purple #8b5cf6

2. Обновить `_make_dark_gradient()` → `_make_gradient(tmpl=None)` — принимает цвета из шаблона
3. Обновить `generate_topic_slide()` — загружает шаблон по design_template параметру и передаёт во все draw-функции
4. Все `_draw_*` и `_render_*` функции — добавить `tmpl` параметр, использовать `tmpl["accent"]`, `tmpl["text"]` вместо глобального TMPL
5. Для светлых шаблонов (clean, warm, creative) — тень текста светлая (#ffffff40), не тёмная

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/services/generator/image.py')"`

---

## ЗАДАЧА 5: NanoBanana — ai_image.py

Переписать файл. Добавить:
1. Промпт-шаблоны для каждой ниши (BACKGROUND_PROMPTS dict)
2. Кеширование: `media/ai_backgrounds/{md5_hash}.jpg`
3. Fallback: если API недоступен или нет ключа → return None
4. Обработка ошибок: httpx.TimeoutException, httpx.HTTPStatusError
5. Логирование каждого вызова

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/services/generator/ai_image.py')"`

---

## ЗАДАЧА 6: Обновить pipeline.py

1. Добавить `from app.utils.niche_configs import get_niche_config`
2. Добавить `use_ai_backgrounds: bool = False` в `generate_topic_carousel_pipeline()`
3. Загружать niche_config: `niche_config = get_niche_config(account.get("niche", "недвижимость"))`
4. Передавать `niche_config=niche_config` в `generate_topic_content()`
5. Если `use_ai_backgrounds=True` и шаблон ≠ expert → вызвать `generate_background()` и использовать как фон
6. Сохранять `niche` и `design_template` в `generation_params`

**Проверка:** `python -c "import py_compile; py_compile.compile('backend/app/services/generator/pipeline.py')"`

---

## ЗАДАЧА 7: API — accounts.py, carousels.py, templates.py

### accounts.py:
- Добавить `design_template: str = "expert"` и `use_ai_backgrounds: bool = False` в AccountCreate/Update
- Добавить `GET /accounts/niches` → вызывает `get_available_niches()`

### carousels.py:
- Добавить `design_template` и `use_ai_backgrounds` в GenerateRequest
- Передать в pipeline

### templates.py:
- Обновить чтобы возвращал все 6 шаблонов

**Проверка:** py_compile на все три файла

---

## ЗАДАЧА 8: Фронтенд — Generator.jsx

1. Добавить state: `selectedNiche`, `selectedTemplate`, `useAIBackgrounds`
2. Fetch `/api/accounts/niches` при загрузке
3. Селектор ниши (dropdown)
4. Сетка шаблонов 3x2 (карточки с цветовыми превью)
5. Чекбокс AI-фоны (если шаблон ≠ expert)
6. Передать `design_template` и `use_ai_backgrounds` в API вызов

---

## ПОРЯДОК: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

После каждого файла — py_compile. Не параллельно.
