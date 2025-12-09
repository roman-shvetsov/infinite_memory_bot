# translations.py
import random
from telegram import ReplyKeyboardMarkup

TRANSLATIONS = {
    'ru': {
        # Команда /start
        'welcome_back': "С возвращением, {name}! 😺\nТвой текущий часовой пояс: {timezone}\nХочешь изменить? Используй /tz\nПомощь: /help\n\nПомни: регулярные повторения = знания навсегда! 🚀",
        'welcome_new': """🚀 *Добро пожаловать в твоего персонального тренера памяти!*

💡 *Знаешь ли ты что?*
• 90% информации мы забываем за первые 24 часа
• Без повторений знания просто "испаряются"
• Можно учить часами и не запомнить ничего

🎯 *А теперь хорошие новости:*
Есть научный способ запоминать информацию *навсегда*!

🔬 *Метод интервального повторения:*
Я напоминаю повторить в идеальные моменты:
• Когда ты вот-вот забудешь
• Чтобы закрепить в долговременной памяти
• Без лишних усилий с твоей стороны

📊 *Всего 7 повторений = знание на годы:*
1 час → 1 день → 3 дня → 1 неделя → 2 недели → 1 месяц → 3 месяца

✨ *Что это тебе даёт:*
• Запоминаешь в 3 раза эффективнее
• Тратишь всего 5-15 минут в день
• Знания остаются с тобой навсегда
• Учишься без стресса и напряжения

🎯 *Начни прямо сейчас:*
1. Выбери язык интерфейса
2. Выбери часовой пояс (чтобы напоминания приходили вовремя)
3. Добавь первую тему
4. Отмечай повторения когда я напоминаю
5. Следи как растёт твоя эрудиция!

Выбери язык:""",

        'help_text': """🚀 Твой персональный тренер памяти - запоминай навсегда!

💡 Научный подход к запоминанию:
Наш мозг забывает информацию по определённой кривой (кривая Эббингауза). 90% информации забывается за первые 24 часа, если её не повторить!

🎯 Почему именно такая последовательность?
1 час - фиксируем в кратковременной памяти
1 день - переносим в среднесрочную память  
3 дня - усиливаем нейронные связи
1-2 недели - закрепляем в долговременную память
1-3 месяца - окончательно фиксируем

📊 Результат: После 7 повторений информация переходит в долговременную память и остаётся с тобой на годы!

🔬 Это не просто цифры:
Метод интервального повторения научно доказан и используется:
• В обучении врачей и пилотов
• При изучении иностранных языков
• В подготовке к серьёзным экзаменам
• Спортсменами для запоминания тактик

🎯 Что можно учить:
• Иностранные слова и фразы
• Научные термины и формулы
• Исторические даты и факты
• Код и алгоритмы
• Подготовка к экзаменам
• И всё что угодно!

🛠 Быстрый старт:
1. Добавь тему - начни с 2-3 тем
2. Отмечай «Повторил!» по напоминаниям
3. Следи за прогрессом - смотри как знания закрепляются
4. Достигай 100% - получай знания навсегда!

📋 Основные команды:
• Добавить тему - создать новую тему
• Мой прогресс - увидеть прогресс
• Категории - организовать темы
• Восстановить тему - повторить завершённое

💫 Попробуй всего 1 тему и увидишь как это работает!
Через неделю ты удивишься сколько запомнил без усилий.

🎉 Готов начать? Нажми «Добавить тему» и убедись сам!

❓ Есть вопросы? Пиши: @garage_pineapple""",

        'categories_limit_info': "\n\n📁 Категорий: {current}/{max}",
        'language_invalid': "❌ Неверный язык. Используйте /language для выбора из списка.",
        # Выбор языка
        'choose_language': "🌍 Выберите язык интерфейса / Choose interface language:",
        'language_set': "✅ Язык установлен: Русский",

        'user_not_found': "Пользователь не найден",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 Все темы сразу",

        'active_topics_count': "📊 Активных тем: {current}/{max}\n",
        'select_category_for_progress': "Выбери категорию для просмотра прогресса:",
        'select_category_to_restore': "Выбери категорию для восстановления тем:",
        'select_category_action': "Выбери действие с категориями:",
        'enter_topic_name': "Напиши название темы, которую хочешь добавить! 😊",

        # Выбор часового пояса
        'choose_timezone': "⏰ Выбери часовой пояс или введи его вручную (например, 'Europe/Moscow' или 'UTC+8'):",
        'timezone_set': "✅ Часовой пояс {timezone} сохранен! 😺",
        'timezone_error': "Ой, что-то не так с часовым поясом. 😔 Попробуй название (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8').",
        'timezone_list_info': "Полный список часовых поясов: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\nОтправь название (например, 'Europe/Moscow') или смещение (например, 'UTC+8' или '+8').",
        'other_manual_button': "Другой (введи вручную)",
        # Основная клавиатура
        'main_keyboard': ["Мой прогресс", "Добавить тему", "Удалить тему", "Восстановить тему", "Категории"],
        'timezone_saved_with_offset': "Часовой пояс {timezone} (UTC{offset}) сохранен! 😺",
        'timezone_saved_simple': "Часовой пояс {timezone} сохранен! 😺",

        # Кнопки
        'cancel': "Отмена",
        'back': "Назад",

        'status_completed': "Завершено",
        'status_overdue': "Просрочено",
        'progress_error': "Ой, что-то пошло не так при отображении прогресса! 😿 Попробуй снова или используй /reset.",

        # Недостающие переводы для русского:
        'enter_timezone_manual': "⌨️ Введи часовой пояс вручную:\n\n• Название: Europe/Moscow, Asia/Tokyo, America/New_York\n• Смещение: +3, UTC+3, -5, UTC-5\n• Или используй /tz list для полного списка",
        'other_manual': "Другой (введи вручную)",
        'tz_button': "/tz",

        'yes': "Да",
        'no': "Нет",

        'select_category_for_topic': "Выбери категорию для темы:",
        'topic_repeated_with_next': "Тема '{topic_name}' отмечена как повторённая! 😺\nЗавершено: {completed}/{total} повторений\nСледующее повторение: {next_time}\nПрогресс: {progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 Поздравляю, ты полностью освоил тему '{topic_name}'! 🏆\nЗавершено: {completed}/{total} повторений\nПрогресс: {progress_bar} {percentage:.1f}%\nЕсли захочешь повторить её заново, используй 'Восстановить тему'. 😺",
        'select_category_to_delete': "Выбери категорию для удаления (темы перейдут в 'Без категории'):",

        # Для тем
        'topic_added': "Тема '{topic_name}' добавлена! 😺 Первое повторение через 1 час.",
        'topic_deleted': "Тема и все связанные напоминания удалены! 😿",
        'topic_not_found': "Тема не найдена. 😿",
        'topic_restored': "Тема '{topic_name}' восстановлена! 😺 Первое повторение через 1 час.",
        'topic_not_found_or_completed': "Тема '{topic_name}' не найдена или уже завершена. 😿 Попробуй снова!",
        'repeated_prefix': "Повторил",

        # Для категорий
        'no_category': "Без категории",
        'category_limit_reached': "❌ Достигнут лимит категорий ({max_categories})! 😿\n\nЧтобы создать новую категорию, сначала удали одну из существующих.\nСейчас у тебя {current_count} категорий.",
        'enter_category_name': "Напиши название новой категории! 😊",
        'select_category_to_rename': "Выбери категорию для переименования:",
        'category_deleted': "Категория удалена! Темы перемещены в 'Без категории'. 😺",
        'category_not_found': "Категория не найдена. 😿",
        'enter_new_category_name': "Напиши новое название категории! 😊",
        'category_renamed': "Категория '{old_name}' переименована в '{new_name}'! 😺",
        'category_created_ask_add_topics': "Категория '{category_name}' создана! 😺 Добавить в неё темы?",
        'category_created_no_topics': "Категория создана без добавления тем! 😺",
        'no_category_with_icon': "📁 Без категории",
        'no_topics_in_category_msg': "В категории '{category_name}' пока нет тем! 😿",

        # Управление темами
        'no_topics_in_category': "В этой категории нет тем для удаления! 😿",
        'no_topics_to_delete': "У тебя нет тем для удаления! 😿",
        'no_completed_topics': "В этой категории нет завершённых тем! 😿",
        'no_completed_topics_all': "У тебя нет завершённых тем для восстановления! 😿",
        'no_topics_to_move': "У тебя нет тем для перемещения! 😿",
        'no_topics_to_add': "У тебя нет тем для добавления! 😿",
        'no_categories_to_rename': "У тебя нет категорий для переименования! 😿",
        'no_categories_to_delete': "У тебя нет категорий для удаления! 😿",
        'progress_header': "📚 {category_name} ({timezone}) 😺\n\n",

        'select_topic_to_delete': "Выбери тему для удаления из категории '{category_name}':",
        'select_topic_to_restore': "Выбери тему для восстановления из категории '{category_name}':",
        'select_topic_to_move': "Выбери тему для перемещения:",
        'select_new_category': "Выбери новую категорию для темы:",
        'topic_moved': "Тема перемещена в категорию '{new_category_name}'! 😺",
        'topic_or_category_not_found': "Тема или категория не найдена. 😿",
        'select_topic_for_new_category': "Выбери тему для добавления в новую категорию:",
        'topic_added_to_category': "Тема добавлена в категорию '{category_name}'! 😺",
        'error_adding_topic': "Ошибка добавления темы. 😿",

        'select_topic_to_delete_all': "Выбери тему для удаления (восстановить будет нельзя):",
        'select_completed_topic_to_restore': "Выбери завершённую тему для восстановления:",
        'too_many_topics': "Слишком много тем для отображения ({count}). Показаны первые 20. Лучше используй выбор по категориям.",
        'too_many_completed_topics': "Слишком много тем для отображения ({count}). Показаны первые 20. Лучше используй выбор по категориям.",

        # Лимиты
        'topic_limit_reached': "❌ Достигнут лимит активных тем ({max_topics})! 😿\n\nЧтобы добавить новую тему, сначала заверши или удали одну из существующих.\nСейчас у тебя {current_count} активных тем.\n\n💡 *Совет:* Лучше сосредоточься на качестве, а не количестве!",

        # Действия с категориями
        'create_category': "Создать категорию",
        'rename_category': "Переименовать категорию",
        'move_topic': "Перенести тему",
        'delete_category': "Удалить категорию",

        'welcome_back_extended': "С возвращением, {name}! 😺\nТвой текущий часовой пояс: {timezone}\nЯзык интерфейса: {language}\nИзменить часовой пояс: /tz\nИзменить язык: /language\nПомощь: /help\n\nПомни: регулярные повторения = знания навсегда! 🚀",
        'russian': "Русский",
        'english': "English",
        'spanish': "Español",
        'chinese': "中文",
        'german': "Deutsch",
        'french': "Français",

        # Прочие сообщения
        'reset_state': "Состояние сброшено! 😺",
        'action_canceled': "Действие отменено! 😺",
        'unknown_command': "Неизвестная команда. 😿",
        'error_occurred': "Ой, что-то пошло не так! 😿 Попробуй снова или используй /reset.",
        'need_timezone': "Пожалуйста, сначала выбери часовой пояс с помощью /tz.",

        # Новые добавленные ключи
        'reminder_time': "⏰ Пора повторить тему '{topic_name}'! 😺",
        'repeated_button': "Повторил!",
        'overdue_reminder': "⏰ Просроченное напоминание! Пора повторить тему '{topic_name}'! 😺",
        'processing_repetition': "Обрабатываю повторение...",
        'user_not_found_error': "Пользователь не найден в базе данных",
        'topic_completed_congrats': "🎉 Поздравляю с завершением темы!",

        # Для ответов на ошибки
        'reminder_not_found': "Напоминание не найдено. Возможно, тема была удалена. 😿",
        'topic_not_found_by_reminder': "Тема не найдена. Возможно, она была удалена. 😿",
        'topic_already_completed': "Эта тема уже завершена! 🎉",
    },

    'en': {
        # Command /start
        'welcome_back': "Welcome back, {name}! 😺\nYour current timezone: {timezone}\nWant to change it? Use /tz\nHelp: /help\n\nRemember: regular repetitions = knowledge forever! 🚀",
        'welcome_new': """🚀 *Welcome to your personal memory trainer!*

💡 *Did you know?*
• 90% of information is forgotten within the first 24 hours
• Without repetition, knowledge simply "evaporates"
• You can study for hours and remember nothing

🎯 *Now the good news:*
There's a scientific way to remember information *forever*!

🔬 *Spaced repetition method:*
I remind you to repeat at optimal times:
• When you're about to forget
• To consolidate into long-term memory
• Without extra effort on your part

📊 *Only 7 repetitions = knowledge for years:*
1 hour → 1 day → 3 days → 1 week → 2 weeks → 1 month → 3 months

✨ *What this gives you:*
• Remember 3 times more effectively
• Spend only 5-15 minutes a day
• Knowledge stays with you forever
• Learn without stress and tension

🎯 *Get started right now:*
1. Choose interface language
2. Choose timezone (so reminders come at the right time)
3. Add your first topic
4. Mark repetitions when I remind you
5. Watch your erudition grow!

Choose language:""",

        'help_text': """🚀 Your personal memory trainer - remember forever!

💡 Scientific approach to memorization:
Our brain forgets information according to a certain curve (Ebbinghaus curve). 90% of information is forgotten within the first 24 hours if not repeated!

🎯 Why this exact sequence?
1 hour - fix in short-term memory
1 day - transfer to medium-term memory  
3 days - strengthen neural connections
1-2 weeks - consolidate into long-term memory
1-3 months - finally fix

📊 Result: After 7 repetitions, information passes into long-term memory and stays with you for years!

🔬 These are not just numbers:
The spaced repetition method is scientifically proven and used:
• In training doctors and pilots
• When studying foreign languages
• In preparation for serious exams
• By athletes for memorizing tactics

🎯 What you can learn:
• Foreign words and phrases
• Scientific terms and formulas
• Historical dates and facts
• Code and algorithms
• Exam preparation
• And anything else!

🛠 Quick start:
1. Add a topic - start with 2-3 topics
2. Mark "Repeated!" on reminders
3. Track progress - watch how knowledge consolidates
4. Reach 100% - get knowledge forever!

📋 Basic commands:
• Add topic - create a new topic
• My progress - see progress
• Categories - organize topics
• Restore topic - repeat completed

💫 Try just 1 topic and see how it works!
In a week you'll be surprised how much you've remembered without effort.

🎉 Ready to start? Click "Add topic" and see for yourself!

❓ Questions? Write: @garage_pineapple""",

        'categories_limit_info': "\n\n📁 Categories: {current}/{max}",
        'language_invalid': "❌ Invalid language. Use /language to choose from the list.",
        # Language selection
        'choose_language': "🌍 Choose interface language:",
        'language_set': "✅ Language set: English",

        'user_not_found': "User not found",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 All topics at once",

        'active_topics_count': "📊 Active topics: {current}/{max}\n",
        'select_category_for_progress': "Select category to view progress:",
        'select_category_to_restore': "Select category to restore topics:",
        'select_category_action': "Select category action:",
        'enter_topic_name': "Write the name of the topic you want to add! 😊",
        'no_category_with_icon': "📁 No category",

        'select_category_for_topic': "Select category for topic:",
        'topic_repeated_with_next': "Topic '{topic_name}' marked as repeated! 😺\nCompleted: {completed}/{total} repetitions\nNext repetition: {next_time}\nProgress: {progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 Congratulations, you've fully mastered the topic '{topic_name}'! 🏆\nCompleted: {completed}/{total} repetitions\nProgress: {progress_bar} {percentage:.1f}%\nIf you want to repeat it again, use 'Restore Topic'. 😺",
        'select_category_to_delete': "Select category to delete (topics will move to 'No category'):",
        'timezone_list_info': "Full list of timezones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\nSend name (e.g., 'Europe/London') or offset (e.g., 'UTC+0' or '+0').",

        # Timezone selection
        'choose_timezone': "⏰ Choose timezone or enter manually (e.g., 'Europe/London' or 'UTC+0'):",
        'timezone_set': "✅ Timezone {timezone} saved! 😺",
        'timezone_error': "Oops, something's wrong with the timezone. 😔 Try a name (e.g., 'Europe/London') or offset (e.g., 'UTC+0' or '+0').",
        'timezone_saved_simple': "Timezone {timezone} saved! 😺",
        'other_manual_button': "Other (enter manually)",
        # Main keyboard
        'main_keyboard': ["My Progress", "Add Topic", "Delete Topic", "Restore Topic", "Categories"],

        # Buttons
        'cancel': "Cancel",
        'back': "Back",

        'status_completed': "Completed",
        'status_overdue': "Overdue",
        'progress_error': "Oops, something went wrong while displaying progress! 😿 Try again or use /reset.",

        # Недостающие переводы для английского:
        'enter_timezone_manual': "⌨️ Enter timezone manually:\n\n• Name: Europe/London, Asia/Tokyo, America/New_York\n• Offset: +0, UTC+0, -5, UTC-5\n• Or use /tz list for full list",
        'other_manual': "Other (enter manually)",
        'tz_button': "/tz",

        'yes': "Yes",
        'no': "No",

        # For topics
        'topic_added': "Topic '{topic_name}' added! 😺 First repetition in 1 hour.",
        'topic_deleted': "Topic and all related reminders deleted! 😿",
        'topic_not_found': "Topic not found. 😿",
        'topic_restored': "Topic '{topic_name}' restored! 😺 First repetition in 1 hour.",
        'topic_not_found_or_completed': "Topic '{topic_name}' not found or already completed. 😿 Try again!",
        'repeated_prefix': "Repeated",

        # For categories
        'no_category': "No category",
        'category_limit_reached': "❌ Category limit reached ({max_categories})! 😿\n\nTo create a new category, first delete one of the existing ones.\nYou currently have {current_count} categories.",
        'enter_category_name': "Write the name of the new category! 😊",
        'select_category_to_rename': "Select category to rename:",
        'category_deleted': "Category deleted! Topics moved to 'No category'. 😺",
        'category_not_found': "Category not found. 😿",
        'enter_new_category_name': "Write the new category name! 😊",
        'category_renamed': "Category '{old_name}' renamed to '{new_name}'! 😺",
        'category_created_ask_add_topics': "Category '{category_name}' created! 😺 Add topics to it?",
        'category_created_no_topics': "Category created without adding topics! 😺",
        'timezone_saved_with_offset': "Timezone {timezone} (UTC{offset}) saved! 😺",
        'no_topics_in_category_msg': "No topics yet in category '{category_name}'! 😿",
        'progress_header': "📚 {category_name} ({timezone}) 😺\n\n",

        # Topic management
        'no_topics_in_category': "No topics to delete in this category! 😿",
        'no_topics_to_delete': "You have no topics to delete! 😿",
        'no_completed_topics': "No completed topics in this category! 😿",
        'no_completed_topics_all': "You have no completed topics to restore! 😿",
        'no_topics_to_move': "You have no topics to move! 😿",
        'no_topics_to_add': "You have no topics to add! 😿",
        'no_categories_to_rename': "You have no categories to rename! 😿",
        'no_categories_to_delete': "You have no categories to delete! 😿",

        'select_topic_to_delete': "Select topic to delete from category '{category_name}':",
        'select_topic_to_restore': "Select topic to restore from category '{category_name}':",
        'select_topic_to_move': "Select topic to move:",
        'select_new_category': "Select new category for topic:",
        'topic_moved': "Topic moved to category '{new_category_name}'! 😺",
        'topic_or_category_not_found': "Topic or category not found. 😿",
        'select_topic_for_new_category': "Select topic to add to new category:",
        'topic_added_to_category': "Topic added to category '{category_name}'! 😺",
        'error_adding_topic': "Error adding topic. 😿",

        'select_topic_to_delete_all': "Select topic to delete (cannot be restored):",
        'select_completed_topic_to_restore': "Select completed topic to restore:",
        'too_many_topics': "Too many topics to display ({count}). Showing first 20. Better use category selection.",
        'too_many_completed_topics': "Too many topics to display ({count}). Showing first 20. Better use category selection.",

        # Limits
        'topic_limit_reached': "❌ Active topics limit reached ({max_topics})! 😿\n\nTo add a new topic, first complete or delete one of the existing ones.\nYou currently have {current_count} active topics.\n\n💡 *Tip:* Focus on quality, not quantity!",

        # Category actions
        'create_category': "Create category",
        'rename_category': "Rename category",
        'move_topic': "Move topic",
        'delete_category': "Delete category",

        'welcome_back_extended': "Welcome back, {name}! 😺\nYour current timezone: {timezone}\nInterface language: {language}\nChange timezone: /tz\nChange language: /language\nHelp: /help\n\nRemember: regular repetitions = knowledge forever! 🚀",
        'russian': "Russian",
        'english': "English",
        'spanish': "Español",
        'chinese': "中文",
        'german': "Deutsch",
        'french': "Français",

        # Other messages
        'reset_state': "State reset! 😺",
        'action_canceled': "Action canceled! 😺",
        'unknown_command': "Unknown command. 😿",
        'error_occurred': "Oops, something went wrong! 😿 Try again or use /reset.",
        'need_timezone': "Please select a timezone first using /tz.",

        # Новые добавленные ключи для английского
        'reminder_time': "⏰ Time to review topic '{topic_name}'! 😺",
        'repeated_button': "Reviewed!",
        'overdue_reminder': "⏰ Overdue reminder! Time to review topic '{topic_name}'! 😺",
        'processing_repetition': "Processing review...",
        'user_not_found_error': "User not found in database",
        'topic_completed_congrats': "🎉 Congratulations on completing the topic!",

        # Для ответов на ошибки
        'reminder_not_found': "Reminder not found. The topic may have been deleted. 😿",
        'topic_not_found_by_reminder': "Topic not found. It may have been deleted. 😿",
        'topic_already_completed': "This topic is already completed! 🎉",
    },

    'es': {  # Испанский
        # Command /start
        'welcome_back': "¡Bienvenido de nuevo, {name}! 😺\nTu zona horaria actual: {timezone}\n¿Quieres cambiarla? Usa /tz\nAyuda: /help\n\n¡Recuerda: ¡repeticiones regulares = conocimiento para siempre! 🚀",
        'welcome_new': """🚀 *¡Bienvenido a tu entrenador de memoria personal!*

💡 *¿Sabías que?*
• 90% de la información se olvida en las primeras 24 horas
• Sin repetición, el conocimiento simplemente se "evapora"
• Puedes estudiar durante horas y no recordar nada

🎯 *Y ahora las buenas noticias:*
¡Hay una forma científica de recordar información *para siempre*!

🔬 *Método de repetición espaciada:*
Te recuerdo repetir en momentos óptimos:
• Cuando estás a punto de olvidar
• Para consolidar en la memoria a largo plazo
• Sin esfuerzo extra de tu parte

📊 *¡Solo 7 repeticiones = conocimiento por años:*
1 hora → 1 día → 3 días → 1 semana → 2 semanas → 1 mes → 3 meses

✨ *¿Qué te da esto?:*
• Recuerdas 3 veces más efectivamente
• Gastas solo 5-15 minutos al día
• El conocimiento se queda contigo para siempre
• Aprendes sin estrés ni tensión

🎯 *¡Comienza ahora mismo!:*
1. Elige el idioma de la interfaz
2. Elige la zona horaria (para que los recordatorios lleguen a tiempo)
3. Añade tu primer tema
4. Marca repeticiones cuando te lo recuerde
5. ¡Observa cómo crece tu erudición!

Elige idioma:""",

        'help_text': """🚀 Tu entrenador de memoria personal - ¡recuerda para siempre!

💡 Enfoque científico para memorizar:
Nuestro cerebro olvida información según una curva determinada (curva de Ebbinghaus). ¡El 90% de la información se olvida en las primeras 24 horas si no se repite!

🎯 ¿Por qué exactamente esta secuencia?
1 hora - fijamos en memoria a corto plazo
1 día - transferimos a memoria a medio plazo  
3 días - fortalecemos conexiones neuronales
1-2 semanas - consolidamos en memoria a largo plazo
1-3 meses - fijamos finalmente

📊 Resultado: ¡Después de 7 repeticiones, la información pasa a la memoria a largo plazo y se queda contigo por años!

🔬 Esto no son solo números:
El método de repetición espaciada está científicamente probado y se usa:
• En la formación de médicos y pilotos
• Al estudiar idiomas extranjeros
• En la preparación para exámenes serios
• Por atletas para memorizar tácticas

🎯 ¿Qué puedes aprender?
• Palabras y frases extranjeras
• Términos y fórmulas científicas
• Fechas y hechos históricos
• Código y algoritmos
• Preparación para exámenes
• ¡Y cualquier otra cosa!

🛠 Inicio rápido:
1. Añade un tema - comienza con 2-3 temas
2. Marca "¡Repetido!" en los recordatorios
3. Sigue el progreso - observa cómo se consolida el conocimiento
4. ¡Alcanza el 100% - obtén conocimiento para siempre!

📋 Comandos básicos:
• Añadir tema - crear un nuevo tema
• Mi progreso - ver el progreso
• Categorías - organizar temas
• Restaurar tema - repetir completado

💫 ¡Prueba solo 1 tema y verás cómo funciona!
En una semana te sorprenderás de cuánto has recordado sin esfuerzo.

🎉 ¿Listo para comenzar? ¡Haz clic en "Añadir tema" y compruébalo tú mismo!

❓ ¿Preguntas? Escribe: @garage_pineapple""",

        'categories_limit_info': "\n\n📁 Categorías: {current}/{max}",
        'language_invalid': "❌ Idioma no válido. Usa /language para elegir de la lista.",
        'choose_language': "🌍 Elige idioma de interfaz:",
        'language_set': "✅ Idioma establecido: Español",
        'user_not_found': "Usuario no encontrado",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 Todos los temas a la vez",
        'active_topics_count': "📊 Temas activos: {current}/{max}\n",
        'select_category_for_progress': "Selecciona categoría para ver progreso:",
        'select_category_to_restore': "Selecciona categoría para restaurar temas:",
        'select_category_action': "Selecciona acción con categorías:",
        'enter_topic_name': "¡Escribe el nombre del tema que quieres añadir! 😊",
        'no_category_with_icon': "📁 Sin categoría",
        'select_category_for_topic': "Selecciona categoría para tema:",
        'topic_repeated_with_next': "¡Tema '{topic_name}' marcado como repetido! 😺\nCompletado: {completed}/{total} repeticiones\nSiguiente repetición: {next_time}\nProgreso: {progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 ¡Felicidades, has dominado completamente el tema '{topic_name}'! 🏆\nCompletado: {completed}/{total} repeticiones\nProgreso: {progress_bar} {percentage:.1f}%\nSi quieres repetirlo de nuevo, usa 'Restaurar Tema'. 😺",
        'select_category_to_delete': "Selecciona categoría para eliminar (los temas irán a 'Sin categoría'):",
        'timezone_list_info': "Lista completa de zonas horarias: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\nEnvía nombre (ej. 'Europe/Madrid') o desplazamiento (ej. 'UTC+1' o '+1').",
        'choose_timezone': "⏰ Elige zona horaria o ingrésala manualmente (ej. 'Europe/Madrid' o 'UTC+1'):",
        'timezone_set': "✅ ¡Zona horaria {timezone} guardada! 😺",
        'timezone_error': "Vaya, algo anda mal con la zona horaria. 😔 Prueba un nombre (ej. 'Europe/Madrid') o desplazamiento (ej. 'UTC+1' o '+1').",
        'timezone_saved_simple': "¡Zona horaria {timezone} guardada! 😺",
        'other_manual_button': "Otro (ingresar manualmente)",
        'main_keyboard': ["Mi Progreso", "Añadir Tema", "Eliminar Tema", "Restaurar Tema", "Categorías"],
        'cancel': "Cancelar",
        'back': "Atrás",
        'status_completed': "Completado",
        'status_overdue': "Vencido",
        'progress_error': "¡Vaya, algo salió mal al mostrar el progreso! 😿 Intenta de nuevo o usa /reset.",
        'enter_timezone_manual': "⌨️ Ingresa zona horaria manualmente:\n\n• Nombre: Europe/Madrid, Asia/Tokyo, America/New_York\n• Desplazamiento: +1, UTC+1, -5, UTC-5\n• O usa /tz list para lista completa",
        'other_manual': "Otro (ingresar manualmente)",
        'tz_button': "/tz",
        'yes': "Sí",
        'no': "No",
        'topic_added': "¡Tema '{topic_name}' añadido! 😺 Primera repetición en 1 hora.",
        'topic_deleted': "¡Tema y todos los recordatorios relacionados eliminados! 😿",
        'topic_not_found': "Tema no encontrado. 😿",
        'topic_restored': "¡Tema '{topic_name}' restaurado! 😺 Primera repetición en 1 hora.",
        'topic_not_found_or_completed': "Tema '{topic_name}' no encontrado o ya completado. 😿 ¡Intenta de nuevo!",
        'repeated_prefix': "Repetido",
        'no_category': "Sin categoría",
        'category_limit_reached': "❌ ¡Límite de categorías alcanzado ({max_categories})! 😿\n\nPara crear una nueva categoría, primero elimina una de las existentes.\nActualmente tienes {current_count} categorías.",
        'enter_category_name': "¡Escribe el nombre de la nueva categoría! 😊",
        'select_category_to_rename': "Selecciona categoría para renombrar:",
        'category_deleted': "¡Categoría eliminada! Temas movidos a 'Sin categoría'. 😺",
        'category_not_found': "Categoría no encontrada. 😿",
        'enter_new_category_name': "¡Escribe el nuevo nombre de categoría! 😊",
        'category_renamed': "¡Categoría '{old_name}' renombrada a '{new_name}'! 😺",
        'category_created_ask_add_topics': "¡Categoría '{category_name}' creada! 😺 ¿Añadir temas a ella?",
        'category_created_no_topics': "¡Categoría creada sin añadir temas! 😺",
        'timezone_saved_with_offset': "¡Zona horaria {timezone} (UTC{offset}) guardada! 😺",
        'no_topics_in_category_msg': "¡Aún no hay temas en la categoría '{category_name}'! 😿",
        'progress_header': "📚 {category_name} ({timezone}) 😺\n\n",
        'no_topics_in_category': "¡No hay temas para eliminar en esta categoría! 😿",
        'no_topics_to_delete': "¡No tienes temas para eliminar! 😿",
        'no_completed_topics': "¡No hay temas completados en esta categoría! 😿",
        'no_completed_topics_all': "¡No tienes temas completados para restaurar! 😿",
        'no_topics_to_move': "¡No tienes temas para mover! 😿",
        'no_topics_to_add': "¡No tienes temas para añadir! 😿",
        'no_categories_to_rename': "¡No tienes categorías para renombrar! 😿",
        'no_categories_to_delete': "¡No tienes categorías para eliminar! 😿",
        'select_topic_to_delete': "Selecciona tema para eliminar de categoría '{category_name}':",
        'select_topic_to_restore': "Selecciona tema para restaurar de categoría '{category_name}':",
        'select_topic_to_move': "Selecciona tema para mover:",
        'select_new_category': "Selecciona nueva categoría para tema:",
        'topic_moved': "¡Tema movido a categoría '{new_category_name}'! 😺",
        'topic_or_category_not_found': "Tema o categoría no encontrada. 😿",
        'select_topic_for_new_category': "Selecciona tema para añadir a nueva categoría:",
        'topic_added_to_category': "¡Tema añadido a categoría '{category_name}'! 😺",
        'error_adding_topic': "Error añadiendo tema. 😿",
        'select_topic_to_delete_all': "Selecciona tema para eliminar (no se podrá restaurar):",
        'select_completed_topic_to_restore': "Selecciona tema completado para restaurar:",
        'too_many_topics': "Demasiados temas para mostrar ({count}). Mostrando primeros 20. Mejor usa selección por categorías.",
        'too_many_completed_topics': "Demasiados temas para mostrar ({count}). Mostrando primeros 20. Mejor usa selección por categorías.",
        'topic_limit_reached': "❌ ¡Límite de temas activos alcanzado ({max_topics})! 😿\n\nPara añadir un nuevo tema, primero completa o elimina uno de los existentes.\nActualmente tienes {current_count} temas activos.\n\n💡 *Consejo:* ¡Enfócate en la calidad, no en la cantidad!",
        'create_category': "Crear categoría",
        'rename_category': "Renombrar categoría",
        'move_topic': "Mover tema",
        'delete_category': "Eliminar categoría",
        'welcome_back_extended': "¡Bienvenido de nuevo, {name}! 😺\nTu zona horaria actual: {timezone}\nIdioma de interfaz: {language}\nCambiar zona horaria: /tz\nCambiar idioma: /language\nAyuda: /help\n\n¡Recuerda: ¡repeticiones regulares = conocimiento para siempre! 🚀",
        'russian': "Ruso",
        'english': "Inglés",
        'spanish': "Español",
        'chinese': "Chino",
        'german': "Alemán",
        'french': "Francés",
        'reset_state': "¡Estado reiniciado! 😺",
        'action_canceled': "¡Acción cancelada! 😺",
        'unknown_command': "Comando desconocido. 😿",
        'error_occurred': "¡Vaya, algo salió mal! 😿 Intenta de nuevo o usa /reset.",
        'need_timezone': "Por favor selecciona una zona horaria primero usando /tz.",
        'reminder_time': "⏰ ¡Hora de repasar el tema '{topic_name}'! 😺",
        'repeated_button': "¡Repasado!",
        'overdue_reminder': "⏰ ¡Recordatorio vencido! Hora de repasar el tema '{topic_name}'! 😺",
        'processing_repetition': "Procesando repaso...",
        'user_not_found_error': "Usuario no encontrado en la base de datos",
        'topic_completed_congrats': "🎉 ¡Felicidades por completar el tema!",
        'reminder_not_found': "Recordatorio no encontrado. El tema puede haber sido eliminado. 😿",
        'topic_not_found_by_reminder': "Tema no encontrado. Puede haber sido eliminado. 😿",
        'topic_already_completed': "¡Este tema ya está completado! 🎉",
    },

    'zh': {  # Китайский (упрощенный)
        # Command /start
        'welcome_back': "欢迎回来，{name}！😺\n您当前的时区：{timezone}\n想更改吗？使用 /tz\n帮助：/help\n\n记住：定期重复 = 知识永远记住！🚀",
        'welcome_new': """🚀 *欢迎来到您的个人记忆训练师！*

💡 *你知道吗？*
• 90%的信息在24小时内被遗忘
• 不重复，知识就会"蒸发"
• 你可以学习数小时却什么也记不住

🎯 *现在有好消息：*
有一种科学的方法可以*永远*记住信息！

🔬 *间隔重复法：*
我在最佳时间提醒您重复：
• 当您快要忘记时
• 为了巩固到长期记忆中
• 无需您额外努力

📊 *仅需7次重复 = 知识保留数年：*
1小时 → 1天 → 3天 → 1周 → 2周 → 1个月 → 3个月

✨ *这给您带来什么？*
• 记忆效率提高3倍
• 每天只需5-15分钟
• 知识永远伴随您
• 无压力无紧张地学习

🎯 *立即开始！*
1. 选择界面语言
2. 选择时区（以便提醒及时到达）
3. 添加第一个主题
4. 我提醒时标记重复
5. 观看您的学识成长！

选择语言：""",

        'help_text': """🚀 您的个人记忆训练师 - 永远记住！

💡 科学的记忆方法：
我们的大脑按照特定曲线（艾宾浩斯曲线）遗忘信息。如果不重复，90%的信息在24小时内被遗忘！

🎯 为什么是这个确切顺序？
1小时 - 固定在短期记忆中
1天 - 转移到中期记忆  
3天 - 加强神经连接
1-2周 - 巩固到长期记忆
1-3个月 - 最终固定

📊 结果：经过7次重复，信息进入长期记忆并伴随您多年！

🔬 这些不仅仅是数字：
间隔重复法经过科学验证并被使用：
• 在医生和飞行员的培训中
• 学习外语时
• 准备重要考试时
• 运动员记忆战术时

🎯 您可以学习什么？
• 外语单词和短语
• 科学术语和公式
• 历史日期和事实
• 代码和算法
• 考试准备
• 以及任何其他东西！

🛠 快速开始：
1. 添加主题 - 从2-3个主题开始
2. 在提醒时标记"已复习！"
3. 跟踪进度 - 观察知识如何巩固
4. 达到100% - 永远获得知识！

📋 基本命令：
• 添加主题 - 创建新主题
• 我的进度 - 查看进度
• 分类 - 组织主题
• 恢复主题 - 重复已完成

💫 尝试仅1个主题，看看效果如何！
一周后您会惊讶于自己轻松记住了多少。

🎉 准备开始？点击"添加主题"亲自验证！

❓ 有问题？写信：@garage_pineapple""",

        'categories_limit_info': "\n\n📁 分类：{current}/{max}",
        'language_invalid': "❌ 语言无效。请使用/language从列表中选择。",
        'choose_language': "🌍 选择界面语言：",
        'language_set': "✅ 语言设置：中文",
        'user_not_found': "用户未找到",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 所有主题一次显示",
        'active_topics_count': "📊 活动主题：{current}/{max}\n",
        'select_category_for_progress': "选择分类查看进度：",
        'select_category_to_restore': "选择分类恢复主题：",
        'select_category_action': "选择分类操作：",
        'enter_topic_name': "写下您想添加的主题名称！😊",
        'no_category_with_icon': "📁 无分类",
        'select_category_for_topic': "为主题选择分类：",
        'topic_repeated_with_next': "主题'{topic_name}'标记为已复习！😺\n完成：{completed}/{total}次重复\n下次复习：{next_time}\n进度：{progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 恭喜，您已完全掌握主题'{topic_name}'！🏆\n完成：{completed}/{total}次重复\n进度：{progress_bar} {percentage:.1f}%\n如果想再次复习，请使用'恢复主题'。😺",
        'select_category_to_delete': "选择要删除的分类（主题将移至'无分类'）：",
        'timezone_list_info': "完整时区列表：https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n发送名称（例如'Asia/Shanghai'）或偏移量（例如'UTC+8'或'+8'）。",
        'choose_timezone': "⏰ 选择时区或手动输入（例如'Asia/Shanghai'或'UTC+8'）：",
        'timezone_set': "✅ 时区{timezone}已保存！😺",
        'timezone_error': "哦，时区有问题。😔 尝试名称（例如'Asia/Shanghai'）或偏移量（例如'UTC+8'或'+8'）。",
        'timezone_saved_simple': "时区{timezone}已保存！😺",
        'other_manual_button': "其他（手动输入）",
        'main_keyboard': ["我的进度", "添加主题", "删除主题", "恢复主题", "分类"],
        'cancel': "取消",
        'back': "返回",
        'status_completed': "已完成",
        'status_overdue': "已过期",
        'progress_error': "哦，显示进度时出错了！😿 请重试或使用/reset。",
        'enter_timezone_manual': "⌨️ 手动输入时区：\n\n• 名称：Asia/Shanghai, Asia/Tokyo, America/New_York\n• 偏移量：+8, UTC+8, -5, UTC-5\n• 或使用/tz list查看完整列表",
        'other_manual': "其他（手动输入）",
        'tz_button': "/tz",
        'yes': "是",
        'no': "否",
        'topic_added': "主题'{topic_name}'已添加！😺 第一次复习在1小时后。",
        'topic_deleted': "主题和所有相关提醒已删除！😿",
        'topic_not_found': "主题未找到。😿",
        'topic_restored': "主题'{topic_name}'已恢复！😺 第一次复习在1小时后。",
        'topic_not_found_or_completed': "主题'{topic_name}'未找到或已完成。😿 请重试！",
        'repeated_prefix': "已复习",
        'no_category': "无分类",
        'category_limit_reached': "❌ 已达到分类限制（{max_categories}）！😿\n\n要创建新分类，请先删除一个现有分类。\n您当前有{current_count}个分类。",
        'enter_category_name': "写下新分类的名称！😊",
        'select_category_to_rename': "选择要重命名的分类：",
        'category_deleted': "分类已删除！主题已移至'无分类'。😺",
        'category_not_found': "分类未找到。😿",
        'enter_new_category_name': "写下新分类名称！😊",
        'category_renamed': "分类'{old_name}'已重命名为'{new_name}'！😺",
        'category_created_ask_add_topics': "分类'{category_name}'已创建！😺 向其中添加主题吗？",
        'category_created_no_topics': "分类已创建，未添加主题！😺",
        'timezone_saved_with_offset': "时区{timezone}（UTC{offset}）已保存！😺",
        'no_topics_in_category_msg': "分类'{category_name}'中还没有主题！😿",
        'progress_header': "📚 {category_name}（{timezone}）😺\n\n",
        'no_topics_in_category': "此分类中没有可删除的主题！😿",
        'no_topics_to_delete': "您没有可删除的主题！😿",
        'no_completed_topics': "此分类中没有已完成主题！😿",
        'no_completed_topics_all': "您没有可恢复的已完成主题！😿",
        'no_topics_to_move': "您没有可移动的主题！😿",
        'no_topics_to_add': "您没有可添加的主题！😿",
        'no_categories_to_rename': "您没有可重命名的分类！😿",
        'no_categories_to_delete': "您没有可删除的分类！😿",
        'select_topic_to_delete': "选择要从分类'{category_name}'中删除的主题：",
        'select_topic_to_restore': "选择要从分类'{category_name}'中恢复的主题：",
        'select_topic_to_move': "选择要移动的主题：",
        'select_new_category': "为主题选择新分类：",
        'topic_moved': "主题已移至分类'{new_category_name}'！😺",
        'topic_or_category_not_found': "主题或分类未找到。😿",
        'select_topic_for_new_category': "选择要添加到新分类的主题：",
        'topic_added_to_category': "主题已添加到分类'{category_name}'！😺",
        'error_adding_topic': "添加主题时出错。😿",
        'select_topic_to_delete_all': "选择要删除的主题（无法恢复）：",
        'select_completed_topic_to_restore': "选择要恢复的已完成主题：",
        'too_many_topics': "要显示的主题太多（{count}）。显示前20个。最好使用分类选择。",
        'too_many_completed_topics': "要显示的主题太多（{count}）。显示前20个。最好使用分类选择。",
        'topic_limit_reached': "❌ 已达到活动主题限制（{max_topics}）！😿\n\n要添加新主题，请先完成或删除一个现有主题。\n您当前有{current_count}个活动主题。\n\n💡 *提示：* 专注于质量，而不是数量！",
        'create_category': "创建分类",
        'rename_category': "重命名分类",
        'move_topic': "移动主题",
        'delete_category': "删除分类",
        'welcome_back_extended': "欢迎回来，{name}！😺\n您当前的时区：{timezone}\n界面语言：{language}\n更改时区：/tz\n更改语言：/language\n帮助：/help\n\n记住：定期重复 = 知识永远记住！🚀",
        'russian': "俄语",
        'english': "英语",
        'spanish': "西班牙语",
        'chinese': "中文",
        'german': "德语",
        'french': "法语",
        'reset_state': "状态已重置！😺",
        'action_canceled': "操作已取消！😺",
        'unknown_command': "未知命令。😿",
        'error_occurred': "哦，出错了！😿 请重试或使用/reset。",
        'need_timezone': "请先使用/tz选择时区。",
        'reminder_time': "⏰ 该复习主题'{topic_name}'了！😺",
        'repeated_button': "已复习！",
        'overdue_reminder': "⏰ 过期提醒！该复习主题'{topic_name}'了！😺",
        'processing_repetition': "处理复习中...",
        'user_not_found_error': "在数据库中未找到用户",
        'topic_completed_congrats': "🎉 恭喜完成主题！",
        'reminder_not_found': "提醒未找到。主题可能已被删除。😿",
        'topic_not_found_by_reminder': "主题未找到。可能已被删除。😿",
        'topic_already_completed': "此主题已完成！🎉",
    },

    'de': {  # Немецкий
        # Command /start
        'welcome_back': "Willkommen zurück, {name}! 😺\nDeine aktuelle Zeitzone: {timezone}\nWillst du sie ändern? Nutze /tz\nHilfe: /help\n\nDenk dran: regelmäßige Wiederholungen = Wissen für immer! 🚀",
        'welcome_new': """🚀 *Willkommen bei deinem persönlichen Gedächtnistrainer!*

💡 *Wusstest du das?*
• 90% der Informationen werden innerhalb der ersten 24 Stunden vergessen
• Ohne Wiederholung "verdampft" Wissen einfach
• Du kannst stundenlang lernen und nichts behalten

🎯 *Und jetzt die gute Nachricht:*
Es gibt eine wissenschaftliche Methode, Informationen *für immer* zu behalten!

🔬 *Spaced-Repetition-Methode:*
Ich erinnere dich zum optimalen Zeitpunkt:
• Wenn du gerade dabei bist, es zu vergessen
• Um es im Langzeitgedächtnis zu festigen
• Ohne zusätzlichen Aufwand von dir

📊 *Nur 7 Wiederholungen = Wissen für Jahre:*
1 Stunde → 1 Tag → 3 Tage → 1 Woche → 2 Wochen → 1 Monat → 3 Monate

✨ *Was dir das bringt:*
• Du behältst 3x effektiver
• Du brauchst nur 5-15 Minuten am Tag
• Wissen bleibt für immer bei dir
• Lernen ohne Stress und Anspannung

🎯 *Starte jetzt sofort:*
1. Wähle die Interface-Sprache
2. Wähle die Zeitzone (damit Erinnerungen rechtzeitig kommen)
3. Füge dein erstes Thema hinzu
4. Markiere Wiederholungen, wenn ich dich erinnere
5. Beobachte, wie dein Wissen wächst!

Wähle Sprache:""",

        'help_text': """🚀 Dein persönlicher Gedächtnistrainer - behalte für immer!

💡 Wissenschaftlicher Ansatz zum Merken:
Unser Gehirn vergisst Informationen nach einer bestimmten Kurve (Ebbinghaus-Kurve). 90% der Informationen werden innerhalb der ersten 24 Stunden vergessen, wenn nicht wiederholt!

🎯 Warum genau diese Abfolge?
1 Stunde - fixieren im Kurzzeitgedächtnis
1 Tag - übertragen ins Mittelfristgedächtnis  
3 Tage - neuronale Verbindungen stärken
1-2 Wochen - im Langzeitgedächtnis festigen
1-3 Monate - endgültig fixieren

📊 Ergebnis: Nach 7 Wiederholungen geht die Information ins Langzeitgedächtnis und bleibt dir für Jahre!

🔬 Das sind nicht nur Zahlen:
Die Spaced-Repetition-Methode ist wissenschaftlich erwiesen und wird eingesetzt:
• In der Ausbildung von Ärzten und Piloten
• Beim Fremdsprachenlernen
• In der Vorbereitung auf ernsthafte Prüfungen
• Von Sportlern zum Merken von Taktiken

🎯 Was kannst du lernen?
• Fremdwörter und Phrasen
• Wissenschaftliche Begriffe und Formeln
• Historische Daten und Fakten
• Code und Algorithmen
• Prüfungsvorbereitung
• Und alles andere!

🛠 Schnellstart:
1. Füge ein Thema hinzu - beginne mit 2-3 Themen
2. Markiere "Wiederholt!" bei Erinnerungen
3. Verfolge den Fortschritt - sieh zu, wie Wissen gefestigt wird
4. Erreiche 100% - erhalte Wissen für immer!

📋 Grundbefehle:
• Thema hinzufügen - neues Thema erstellen
• Mein Fortschritt - Fortschritt sehen
• Kategorien - Themen organisieren
• Thema wiederherstellen - abgeschlossenes wiederholen

💫 Probiere nur 1 Thema und sieh, wie es funktioniert!
In einer Woche wirst du erstaunt sein, wie viel du mühelos behalten hast.

🎉 Bereit zu starten? Klicke auf "Thema hinzufügen" und überzeuge dich selbst!

❓ Fragen? Schreib: @garage_pineapple""",

        'categories_limit_info': "\n\n📁 Kategorien: {current}/{max}",
        'language_invalid': "❌ Ungültige Sprache. Nutze /language für die Auswahl.",
        'choose_language': "🌍 Interface-Sprache wählen:",
        'language_set': "✅ Sprache eingestellt: Deutsch",
        'user_not_found': "Benutzer nicht gefunden",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 Alle Themen auf einmal",
        'active_topics_count': "📊 Aktive Themen: {current}/{max}\n",
        'select_category_for_progress': "Kategorie für Fortschritt wählen:",
        'select_category_to_restore': "Kategorie zur Wiederherstellung wählen:",
        'select_category_action': "Kategorie-Aktion wählen:",
        'enter_topic_name': "Schreib den Namen des Themas, das du hinzufügen möchtest! 😊",
        'no_category_with_icon': "📁 Keine Kategorie",
        'select_category_for_topic': "Kategorie für Thema wählen:",
        'topic_repeated_with_next': "Thema '{topic_name}' als wiederholt markiert! 😺\nAbgeschlossen: {completed}/{total} Wiederholungen\nNächste Wiederholung: {next_time}\nFortschritt: {progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 Glückwunsch, du hast das Thema '{topic_name}' vollständig gemeistert! 🏆\nAbgeschlossen: {completed}/{total} Wiederholungen\nFortschritt: {progress_bar} {percentage:.1f}%\nWenn du es erneut wiederholen möchtest, nutze 'Thema wiederherstellen'. 😺",
        'select_category_to_delete': "Kategorie zum Löschen wählen (Themen gehen in 'Keine Kategorie'):",
        'timezone_list_info': "Vollständige Zeitzonenliste: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\nSende Namen (z.B. 'Europe/Berlin') oder Offset (z.B. 'UTC+1' oder '+1').",
        'choose_timezone': "⏰ Zeitzone wählen oder manuell eingeben (z.B. 'Europe/Berlin' oder 'UTC+1'):",
        'timezone_set': "✅ Zeitzone {timezone} gespeichert! 😺",
        'timezone_error': "Hoppla, etwas stimmt mit der Zeitzone nicht. 😔 Versuche einen Namen (z.B. 'Europe/Berlin') oder Offset (z.B. 'UTC+1' oder '+1').",
        'timezone_saved_simple': "Zeitzone {timezone} gespeichert! 😺",
        'other_manual_button': "Andere (manuell eingeben)",
        'main_keyboard': ["Mein Fortschritt", "Thema hinzufügen", "Thema löschen", "Thema wiederherstellen",
                          "Kategorien"],
        'cancel': "Abbrechen",
        'back': "Zurück",
        'status_completed': "Abgeschlossen",
        'status_overdue': "Überfällig",
        'progress_error': "Hoppla, beim Anzeigen des Fortschritts ist etwas schiefgelaufen! 😿 Versuch es erneut oder nutze /reset.",
        'enter_timezone_manual': "⌨️ Zeitzone manuell eingeben:\n\n• Name: Europe/Berlin, Asia/Tokyo, America/New_York\n• Offset: +1, UTC+1, -5, UTC-5\n• Oder nutze /tz list für vollständige Liste",
        'other_manual': "Andere (manuell eingeben)",
        'tz_button': "/tz",
        'yes': "Ja",
        'no': "Nein",
        'topic_added': "Thema '{topic_name}' hinzugefügt! 😺 Erste Wiederholung in 1 Stunde.",
        'topic_deleted': "Thema und alle zugehörigen Erinnerungen gelöscht! 😿",
        'topic_not_found': "Thema nicht gefunden. 😿",
        'topic_restored': "Thema '{topic_name}' wiederhergestellt! 😺 Erste Wiederholung in 1 Stunde.",
        'topic_not_found_or_completed': "Thema '{topic_name}' nicht gefunden oder bereits abgeschlossen. 😿 Versuch es erneut!",
        'repeated_prefix': "Wiederholt",
        'no_category': "Keine Kategorie",
        'category_limit_reached': "❌ Kategorien-Limit erreicht ({max_categories})! 😿\n\nUm eine neue Kategorie zu erstellen, lösche zuerst eine vorhandene.\nDu hast aktuell {current_count} Kategorien.",
        'enter_category_name': "Schreib den Namen der neuen Kategorie! 😊",
        'select_category_to_rename': "Kategorie zum Umbenennen wählen:",
        'category_deleted': "Kategorie gelöscht! Themen nach 'Keine Kategorie' verschoben. 😺",
        'category_not_found': "Kategorie nicht gefunden. 😿",
        'enter_new_category_name': "Schreib den neuen Kategorienamen! 😊",
        'category_renamed': "Kategorie '{old_name}' in '{new_name}' umbenannt! 😺",
        'category_created_ask_add_topics': "Kategorie '{category_name}' erstellt! 😺 Themen hinzufügen?",
        'category_created_no_topics': "Kategorie ohne Themen erstellt! 😺",
        'timezone_saved_with_offset': "Zeitzone {timezone} (UTC{offset}) gespeichert! 😺",
        'no_topics_in_category_msg': "Noch keine Themen in Kategorie '{category_name}'! 😿",
        'progress_header': "📚 {category_name} ({timezone}) 😺\n\n",
        'no_topics_in_category': "Keine Themen zum Löschen in dieser Kategorie! 😿",
        'no_topics_to_delete': "Du hast keine Themen zum Löschen! 😿",
        'no_completed_topics': "Keine abgeschlossenen Themen in dieser Kategorie! 😿",
        'no_completed_topics_all': "Du hast keine abgeschlossenen Themen zum Wiederherstellen! 😿",
        'no_topics_to_move': "Du hast keine Themen zum Verschieben! 😿",
        'no_topics_to_add': "Du hast keine Themen zum Hinzufügen! 😿",
        'no_categories_to_rename': "Du hast keine Kategorien zum Umbenennen! 😿",
        'no_categories_to_delete': "Du hast keine Kategorien zum Löschen! 😿",
        'select_topic_to_delete': "Thema zum Löschen aus Kategorie '{category_name}' wählen:",
        'select_topic_to_restore': "Thema zur Wiederherstellung aus Kategorie '{category_name}' wählen:",
        'select_topic_to_move': "Thema zum Verschieben wählen:",
        'select_new_category': "Neue Kategorie für Thema wählen:",
        'topic_moved': "Thema in Kategorie '{new_category_name}' verschoben! 😺",
        'topic_or_category_not_found': "Thema oder Kategorie nicht gefunden. 😿",
        'select_topic_for_new_category': "Thema zum Hinzufügen zur neuen Kategorie wählen:",
        'topic_added_to_category': "Thema zu Kategorie '{category_name}' hinzugefügt! 😺",
        'error_adding_topic': "Fehler beim Hinzufügen des Themas. 😿",
        'select_topic_to_delete_all': "Thema zum Löschen wählen (kann nicht wiederhergestellt werden):",
        'select_completed_topic_to_restore': "Abgeschlossenes Thema zur Wiederherstellung wählen:",
        'too_many_topics': "Zu viele Themen zum Anzeigen ({count}). Zeige erste 20. Besser Kategorieauswahl nutzen.",
        'too_many_completed_topics': "Zu viele Themen zum Anzeigen ({count}). Zeige erste 20. Besser Kategorieauswahl nutzen.",
        'topic_limit_reached': "❌ Limit aktiver Themen erreicht ({max_topics})! 😿\n\nUm ein neues Thema hinzuzufügen, schließe oder lösche zuerst ein vorhandenes.\nDu hast aktuell {current_count} aktive Themen.\n\n💡 *Tipp:* Konzentriere dich auf Qualität, nicht Quantität!",
        'create_category': "Kategorie erstellen",
        'rename_category': "Kategorie umbenennen",
        'move_topic': "Thema verschieben",
        'delete_category': "Kategorie löschen",
        'welcome_back_extended': "Willkommen zurück, {name}! 😺\nDeine aktuelle Zeitzone: {timezone}\nInterface-Sprache: {language}\nZeitzone ändern: /tz\nSprache ändern: /language\nHilfe: /help\n\nDenk dran: regelmäßige Wiederholungen = Wissen für immer! 🚀",
        'russian': "Russisch",
        'english': "Englisch",
        'spanish': "Spanisch",
        'chinese': "Chinesisch",
        'german': "Deutsch",
        'french': "Französisch",
        'reset_state': "Status zurückgesetzt! 😺",
        'action_canceled': "Aktion abgebrochen! 😺",
        'unknown_command': "Unbekannter Befehl. 😿",
        'error_occurred': "Hoppla, etwas ist schiefgelaufen! 😿 Versuch es erneut oder nutze /reset.",
        'need_timezone': "Bitte wähle zuerst eine Zeitzone mit /tz.",
        'reminder_time': "⏰ Zeit, das Thema '{topic_name}' zu wiederholen! 😺",
        'repeated_button': "Wiederholt!",
        'overdue_reminder': "⏰ Überfällige Erinnerung! Zeit, das Thema '{topic_name}' zu wiederholen! 😺",
        'processing_repetition': "Wiederholung wird verarbeitet...",
        'user_not_found_error': "Benutzer in Datenbank nicht gefunden",
        'topic_completed_congrats': "🎉 Glückwunsch zum Abschluss des Themas!",
        'reminder_not_found': "Erinnerung nicht gefunden. Das Thema wurde möglicherweise gelöscht. 😿",
        'topic_not_found_by_reminder': "Thema nicht gefunden. Es wurde möglicherweise gelöscht. 😿",
        'topic_already_completed': "Dieses Thema ist bereits abgeschlossen! 🎉",
    },

    'fr': {  # Французский
        # Command /start
        'welcome_back': "Bienvenue de retour, {name} ! 😺\nVotre fuseau horaire actuel : {timezone}\nVous voulez le changer ? Utilisez /tz\nAide : /help\n\nRappelez-vous : répétitions régulières = connaissances pour toujours ! 🚀",
        'welcome_new': """🚀 *Bienvenue dans votre entraîneur de mémoire personnel !*

💡 *Le saviez-vous ?*
• 90% des informations sont oubliées dans les premières 24 heures
• Sans répétition, les connaissances "s'évaporent" simplement
• Vous pouvez étudier pendant des heures et ne rien retenir

🎯 *Et maintenant la bonne nouvelle :*
Il existe une méthode scientifique pour retenir les informations *pour toujours* !

🔬 *Méthode de répétition espacée :*
Je vous rappelle de répéter au moment optimal :
• Quand vous êtes sur le point d'oublier
• Pour consolider dans la mémoire à long terme
• Sans effort supplémentaire de votre part

📊 *Seulement 7 répétitions = connaissance pour des années :*
1 heure → 1 jour → 3 jours → 1 semaine → 2 semaines → 1 mois → 3 mois

✨ *Ce que cela vous apporte :*
• Vous retenez 3 fois plus efficacement
• Vous ne passez que 5 à 15 minutes par jour
• Les connaissances restent avec vous pour toujours
• Apprenez sans stress ni tension

🎯 *Commencez dès maintenant !*
1. Choisissez la langue de l'interface
2. Choisissez le fuseau horaire (pour que les rappels arrivent à temps)
3. Ajoutez votre premier sujet
4. Marquez les répétitions quand je vous le rappelle
5. Observez votre érudition grandir !

Choisissez la langue :""",

        'help_text': """🚀 Votre entraîneur de mémoire personnel - retenez pour toujours !

💡 Approche scientifique de la mémorisation :
Notre cerveau oublie les informations selon une certaine courbe (courbe d'Ebbinghaus). 90% des informations sont oubliées dans les premières 24 heures si elles ne sont pas répétées !

🎯 Pourquoi exactement cette séquence ?
1 heure - fixer dans la mémoire à court terme
1 jour - transférer dans la mémoire à moyen terme  
3 jours - renforcer les connexions neuronales
1-2 semaines - consolider dans la mémoire à long terme
1-3 mois - fixer définitivement

📊 Résultat : Après 7 répétitions, l'information passe dans la mémoire à long terme et reste avec vous pendant des années !

🔬 Ce ne sont pas que des chiffres :
La méthode de répétition espacée est scientifiquement prouvée et utilisée :
• Dans la formation des médecins et des pilotes
• Lors de l'apprentissage des langues étrangères
• Dans la préparation aux examens sérieux
• Par les athlètes pour mémoriser les tactiques

🎯 Que pouvez-vous apprendre ?
• Mots et phrases étrangers
• Termes et formules scientifiques
• Dates et faits historiques
• Code et algorithmes
• Préparation aux examens
• Et tout le reste !

🛠 Démarrage rapide :
1. Ajoutez un sujet - commencez par 2-3 sujets
2. Marquez "Répété !" sur les rappels
3. Suivez la progression - observez comment les connaissances se consolident
4. Atteignez 100% - obtenez des connaissances pour toujours !

📋 Commandes de base :
• Ajouter un sujet - créer un nouveau sujet
• Ma progression - voir la progression
• Catégories - organiser les sujets
• Restaurer le sujet - répéter le terminé

💫 Essayez juste 1 sujet et voyez comment ça fonctionne !
Dans une semaine, vous serez surpris de combien vous avez retenu sans effort.

🎉 Prêt à commencer ? Cliquez sur "Ajouter un sujet" et voyez par vous-même !

❓ Des questions ? Écrivez : @garage_pineapple""",

        'categories_limit_info': "\n\n📁 Catégories : {current}/{max}",
        'language_invalid': "❌ Langue invalide. Utilisez /language pour choisir dans la liste.",
        'choose_language': "🌍 Choisissez la langue de l'interface :",
        'language_set': "✅ Langue définie : Français",
        'user_not_found': "Utilisateur non trouvé",
        'no_category_icon': "📁",
        'all_topics_at_once': "🔍 Tous les sujets à la fois",
        'active_topics_count': "📊 Sujets actifs : {current}/{max}\n",
        'select_category_for_progress': "Sélectionnez une catégorie pour voir la progression :",
        'select_category_to_restore': "Sélectionnez une catégorie pour restaurer les sujets :",
        'select_category_action': "Sélectionnez une action avec les catégories :",
        'enter_topic_name': "Écrivez le nom du sujet que vous voulez ajouter ! 😊",
        'no_category_with_icon': "📁 Sans catégorie",
        'select_category_for_topic': "Sélectionnez une catégorie pour le sujet :",
        'topic_repeated_with_next': "Sujet '{topic_name}' marqué comme répété ! 😺\nTerminé : {completed}/{total} répétitions\nProchaine répétition : {next_time}\nProgression : {progress_bar} {percentage:.1f}%",
        'topic_completed': "🎉 Félicitations, vous avez maîtrisé complètement le sujet '{topic_name}' ! 🏆\nTerminé : {completed}/{total} répétitions\nProgression : {progress_bar} {percentage:.1f}%\nSi vous voulez le répéter à nouveau, utilisez 'Restaurer le sujet'. 😺",
        'select_category_to_delete': "Sélectionnez une catégorie à supprimer (les sujets iront dans 'Sans catégorie') :",
        'timezone_list_info': "Liste complète des fuseaux horaires : https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\nEnvoyez un nom (ex. 'Europe/Paris') ou un décalage (ex. 'UTC+1' ou '+1').",
        'choose_timezone': "⏰ Choisissez un fuseau horaire ou entrez-le manuellement (ex. 'Europe/Paris' ou 'UTC+1') :",
        'timezone_set': "✅ Fuseau horaire {timezone} sauvegardé ! 😺",
        'timezone_error': "Oups, quelque chose ne va pas avec le fuseau horaire. 😔 Essayez un nom (ex. 'Europe/Paris') ou un décalage (ex. 'UTC+1' ou '+1').",
        'timezone_saved_simple': "Fuseau horaire {timezone} sauvegardé ! 😺",
        'other_manual_button': "Autre (entrer manuellement)",
        'main_keyboard': ["Ma Progression", "Ajouter un Sujet", "Supprimer un Sujet", "Restaurer un Sujet",
                          "Catégories"],
        'cancel': "Annuler",
        'back': "Retour",
        'status_completed': "Terminé",
        'status_overdue': "En retard",
        'progress_error': "Oups, quelque chose s'est mal passé en affichant la progression ! 😿 Réessayez ou utilisez /reset.",
        'enter_timezone_manual': "⌨️ Entrez manuellement le fuseau horaire :\n\n• Nom : Europe/Paris, Asia/Tokyo, America/New_York\n• Décalage : +1, UTC+1, -5, UTC-5\n• Ou utilisez /tz list pour la liste complète",
        'other_manual': "Autre (entrer manuellement)",
        'tz_button': "/tz",
        'yes': "Oui",
        'no': "Non",
        'topic_added': "Sujet '{topic_name}' ajouté ! 😺 Première répétition dans 1 heure.",
        'topic_deleted': "Sujet et tous les rappels associés supprimés ! 😿",
        'topic_not_found': "Sujet non trouvé. 😿",
        'topic_restored': "Sujet '{topic_name}' restauré ! 😺 Première répétition dans 1 heure.",
        'topic_not_found_or_completed': "Sujet '{topic_name}' non trouvé ou déjà terminé. 😿 Réessayez !",
        'repeated_prefix': "Répété",
        'no_category': "Sans catégorie",
        'category_limit_reached': "❌ Limite de catégories atteinte ({max_categories}) ! 😿\n\nPour créer une nouvelle catégorie, supprimez d'abord une existante.\nVous avez actuellement {current_count} catégories.",
        'enter_category_name': "Écrivez le nom de la nouvelle catégorie ! 😊",
        'select_category_to_rename': "Sélectionnez une catégorie à renommer :",
        'category_deleted': "Catégorie supprimée ! Sujets déplacés vers 'Sans catégorie'. 😺",
        'category_not_found': "Catégorie non trouvée. 😿",
        'enter_new_category_name': "Écrivez le nouveau nom de catégorie ! 😊",
        'category_renamed': "Catégorie '{old_name}' renommée en '{new_name}' ! 😺",
        'category_created_ask_add_topics': "Catégorie '{category_name}' créée ! 😺 Ajouter des sujets ?",
        'category_created_no_topics': "Catégorie créée sans ajouter de sujets ! 😺",
        'timezone_saved_with_offset': "Fuseau horaire {timezone} (UTC{offset}) sauvegardé ! 😺",
        'no_topics_in_category_msg': "Pas encore de sujets dans la catégorie '{category_name}' ! 😿",
        'progress_header': "📚 {category_name} ({timezone}) 😺\n\n",
        'no_topics_in_category': "Aucun sujet à supprimer dans cette catégorie ! 😿",
        'no_topics_to_delete': "Vous n'avez aucun sujet à supprimer ! 😿",
        'no_completed_topics': "Aucun sujet terminé dans cette catégorie ! 😿",
        'no_completed_topics_all': "Vous n'avez aucun sujet terminé à restaurer ! 😿",
        'no_topics_to_move': "Vous n'avez aucun sujet à déplacer ! 😿",
        'no_topics_to_add': "Vous n'avez aucun sujet à ajouter ! 😿",
        'no_categories_to_rename': "Vous n'avez aucune catégorie à renommer ! 😿",
        'no_categories_to_delete': "Vous n'avez aucune catégorie à supprimer ! 😿",
        'select_topic_to_delete': "Sélectionnez un sujet à supprimer de la catégorie '{category_name}' :",
        'select_topic_to_restore': "Sélectionnez un sujet à restaurer de la catégorie '{category_name}' :",
        'select_topic_to_move': "Sélectionnez un sujet à déplacer :",
        'select_new_category': "Sélectionnez une nouvelle catégorie pour le sujet :",
        'topic_moved': "Sujet déplacé vers la catégorie '{new_category_name}' ! 😺",
        'topic_or_category_not_found': "Sujet ou catégorie non trouvé. 😿",
        'select_topic_for_new_category': "Sélectionnez un sujet à ajouter à la nouvelle catégorie :",
        'topic_added_to_category': "Sujet ajouté à la catégorie '{category_name}' ! 😺",
        'error_adding_topic': "Erreur en ajoutant le sujet. 😿",
        'select_topic_to_delete_all': "Sélectionnez un sujet à supprimer (ne pourra pas être restauré) :",
        'select_completed_topic_to_restore': "Sélectionnez un sujet terminé à restaurer :",
        'too_many_topics': "Trop de sujets à afficher ({count}). Affichage des 20 premiers. Mieux vaut utiliser la sélection par catégorie.",
        'too_many_completed_topics': "Trop de sujets à afficher ({count}). Affichage des 20 premiers. Mieux vaut utiliser la sélection par catégorie.",
        'topic_limit_reached': "❌ Limite de sujets actifs atteinte ({max_topics}) ! 😿\n\nPour ajouter un nouveau sujet, terminez ou supprimez d'abord un sujet existant.\nVous avez actuellement {current_count} sujets actifs.\n\n💡 *Conseil :* Concentrez-vous sur la qualité, pas la quantité !",
        'create_category': "Créer une catégorie",
        'rename_category': "Renommer une catégorie",
        'move_topic': "Déplacer un sujet",
        'delete_category': "Supprimer une catégorie",
        'welcome_back_extended': "Bienvenue de retour, {name} ! 😺\nVotre fuseau horaire actuel : {timezone}\nLangue de l'interface : {language}\nChanger le fuseau horaire : /tz\nChanger la langue : /language\nAide : /help\n\nRappelez-vous : répétitions régulières = connaissances pour toujours ! 🚀",
        'russian': "Russe",
        'english': "Anglais",
        'spanish': "Espagnol",
        'chinese': "Chinois",
        'german': "Allemand",
        'french': "Français",
        'reset_state': "État réinitialisé ! 😺",
        'action_canceled': "Action annulée ! 😺",
        'unknown_command': "Commande inconnue. 😿",
        'error_occurred': "Oups, quelque chose s'est mal passé ! 😿 Réessayez ou utilisez /reset.",
        'need_timezone': "Veuillez d'abord sélectionner un fuseau horaire en utilisant /tz.",
        'reminder_time': "⏰ Il est temps de revoir le sujet '{topic_name}' ! 😺",
        'repeated_button': "Revisité !",
        'overdue_reminder': "⏰ Rappel en retard ! Il est temps de revoir le sujet '{topic_name}' ! 😺",
        'processing_repetition': "Traitement de la révision...",
        'user_not_found_error': "Utilisateur non trouvé dans la base de données",
        'topic_completed_congrats': "🎉 Félicitations pour avoir terminé le sujet !",
        'reminder_not_found': "Rappel non trouvé. Le sujet a peut-être été supprimé. 😿",
        'topic_not_found_by_reminder': "Sujet non trouvé. Il a peut-être été supprimé. 😿",
        'topic_already_completed': "Ce sujet est déjà terminé ! 🎉",
    },
}

# Сообщения Кекса для разных настроений и ситуаций
KEX_MESSAGES = {
    'ru': {
        "friendly": [
            {
                "text": "Привет! Кексик тут 🐱 Твои темы соскучились по тебе! Небольшое повторение - и ты снова в ритме!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Эй-эй! Кексик на связи 😺 Твои знания ждут не дождутся, когда ты их освежишь! Всего 5 минут - и ты молодец!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Мяу! Кексик тут 🐾 Помнишь, как здорово было видеть прогресс? Давай продолжим! Твои темы ждут!",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Кексик грустит... 😿 Твои темы давно не видели повторений. Всего пару минут - и я снова буду мурлыкать!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Эх... Кексик сидит одинокий 🐱 Твои знания потихоньку забываются. Давай не дадим им исчезнуть!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Кексик вздыхает... Ты так хорошо начинал! Не бросай сейчас - просто зайди и отметь пару повторений!",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "Кексик сердит! 😾 Ты обещал заниматься регулярно! Хватит откладывать - время действовать!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "Фррр! Кексик недоволен! Твои темы покрываются пылью! Соберись и продолжи путь к знаниям!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "ШШШ! Кексик в ярости! Столько усилий - и всё насмарку? Нет! Вернись и доведи начатое до конца!",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "Всё. Кексик сдаётся. 😾 Я больше не буду напоминать. Если хочешь - возвращайся сам. Прощай.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Это последнее напоминание. Кексик устал бороться с твоим безразличием. Решай сам, нужны ли тебе знания.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Кексик опускает лапки. Я сделал всё, что мог. Больше напоминаний не будет. Надеюсь, ты одумаешься.",
                "image": "kex_final_1.png"
            }
        ]
    },
    'en': {
        "friendly": [
            {
                "text": "Hi! Keksik here 🐱 Your topics miss you! A little review - and you're back in rhythm!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Hey-hey! Keksik on the line 😺 Your knowledge can't wait for you to refresh it! Just 5 minutes - and you're great!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Meow! Keksik here 🐾 Remember how great it was to see progress? Let's continue! Your topics are waiting!",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Keksik is sad... 😿 Your topics haven't seen repetitions for a long time. Just a couple of minutes - and I'll be purring again!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Oh... Keksik sits alone 🐱 Your knowledge is slowly being forgotten. Let's not let it disappear!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Keksik sighs... You started so well! Don't quit now - just come in and mark a couple of repetitions!",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "Keksik is angry! 😾 You promised to study regularly! Stop procrastinating - time to act!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "Frrr! Keksik is unhappy! Your topics are gathering dust! Get yourself together and continue the path to knowledge!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "SSH! Keksik is furious! So much effort - and everything is gone? No! Come back and finish what you started!",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "That's it. Keksik gives up. 😾 I won't remind you anymore. If you want - come back on your own. Goodbye.",
                "image": "kex_final_1.png"
            },
            {
                "text": "This is the last reminder. Keksik is tired of fighting your indifference. Decide for yourself if you need knowledge.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Keksik lowers his paws. I did everything I could. No more reminders. I hope you come to your senses.",
                "image": "kex_final_1.png"
            }
        ]
    },
    'es': {  # Испанский
        "friendly": [
            {
                "text": "¡Hola! Keksik aquí 🐱 ¡Tus temas te extrañan! ¡Un pequeño repaso - y estarás de vuelta en ritmo!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "¡Hola-hola! Keksik en la línea 😺 ¡Tu conocimiento no puede esperar a que lo actualices! ¡Solo 5 minutos - y serás genial!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "¡Miau! Keksik aquí 🐾 ¿Recuerdas lo genial que era ver el progreso? ¡Continuemos! ¡Tus temas te esperan!",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Keksik está triste... 😿 Tus temas no han visto repeticiones durante mucho tiempo. ¡Solo un par de minutos - y estaré ronroneando de nuevo!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Oh... Keksik se sienta solo 🐱 Tu conocimiento se está olvidando lentamente. ¡No dejemos que desaparezca!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Keksik suspira... ¡Comenzaste tan bien! ¡No te rindas ahora - solo entra y marca un par de repeticiones!",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "¡Keksik está enojado! 😾 ¡Prometiste estudiar regularmente! ¡Deja de procrastinar - es hora de actuar!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "¡Frrr! ¡Keksik está descontento! ¡Tus temas están acumulando polvo! ¡Reúnete y continúa el camino hacia el conocimiento!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "¡SSH! ¡Keksik está furioso! ¿Tanto esfuerzo - y todo se ha ido? ¡No! ¡Vuelve y termina lo que comenzaste!",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "Eso es todo. Keksik se rinde. 😾 Ya no te recordaré. Si quieres - vuelve por tu cuenta. Adiós.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Este es el último recordatorio. Keksik está cansado de luchar contra tu indiferencia. Decide por ti mismo si necesitas conocimiento.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Keksik baja sus patas. Hice todo lo que pude. No más recordatorios. Espero que recapacites.",
                "image": "kex_final_1.png"
            }
        ]
    },
    'zh': {  # Китайский
        "friendly": [
            {
                "text": "嗨！Keksik在这里🐱你的主题想你了！一个小小的复习 - 你就会回到节奏中！",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "嘿-嘿！Keksik在线😺你的知识迫不及待等你刷新它！只需5分钟 - 你就会很棒！",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "喵！Keksik在这里🐾记得看到进步有多棒吗？让我们继续！你的主题在等待！",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Keksik很难过...😿你的主题很久没有看到重复了。只需几分钟 - 我又会咕噜咕噜了！",
                "image": "kex_sad_1.png"
            },
            {
                "text": "哦...Keksik独自坐着🐱你的知识正在慢慢被遗忘。让我们不要让它消失！",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Keksik叹气...你开始得这么好！现在不要放弃 - 只是进来标记几个重复！",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "Keksik生气了！😾你承诺定期学习！停止拖延 - 是时候行动了！",
                "image": "kex_angry_1.png"
            },
            {
                "text": "Frrr！Keksik不高兴！你的主题正在积灰！振作起来，继续通往知识的道路！",
                "image": "kex_angry_1.png"
            },
            {
                "text": "SSH！Keksik暴怒了！这么多努力 - 一切都消失了？不！回来完成你开始的事情！",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "就这样。Keksik放弃了。😾我不会再提醒你了。如果你想要 - 自己回来。再见。",
                "image": "kex_final_1.png"
            },
            {
                "text": "这是最后的提醒。Keksik厌倦了与你的冷漠作斗争。自己决定是否需要知识。",
                "image": "kex_final_1.png"
            },
            {
                "text": "Keksik放下了爪子。我做了我能做的一切。不再有提醒了。我希望你能醒悟过来。",
                "image": "kex_final_1.png"
            }
        ]
    },
    'de': {  # Немецкий
        "friendly": [
            {
                "text": "Hallo! Keksik hier 🐱 Deine Themen vermissen dich! Eine kleine Wiederholung - und du bist wieder im Rhythmus!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Hey-hey! Keksik am Apparat 😺 Dein Wissen kann es kaum erwarten, dass du es auffrischst! Nur 5 Minuten - und du bist großartig!",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Miau! Keksik hier 🐾 Erinnerst du dich, wie toll es war, Fortschritt zu sehen? Lass uns weitermachen! Deine Themen warten!",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Keksik ist traurig... 😿 Deine Themen haben lange keine Wiederholungen gesehen. Nur ein paar Minuten - und ich schnurre wieder!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Oh... Keksik sitzt allein 🐱 Dein Wissen wird langsam vergessen. Lass es nicht verschwinden!",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Keksik seufzt... Du hast so gut angefangen! Gib jetzt nicht auf - komm einfach rein und markiere ein paar Wiederholungen!",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "Keksik ist wütend! 😾 Du hast versprochen, regelmäßig zu lernen! Hör auf zu prokrastinieren - Zeit zu handeln!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "Frrr! Keksik ist unzufrieden! Deine Themen sammeln Staub! Reiß dich zusammen und setze den Weg zum Wissen fort!",
                "image": "kex_angry_1.png"
            },
            {
                "text": "SSH! Keksik ist wütend! So viel Mühe - und alles ist weg? Nein! Komm zurück und beende, was du angefangen hast!",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "Das war's. Keksik gibt auf. 😾 Ich werde dich nicht mehr erinnern. Wenn du willst - komm selbst zurück. Auf Wiedersehen.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Das ist die letzte Erinnerung. Keksik ist müde, gegen deine Gleichgültigkeit zu kämpfen. Entscheide selbst, ob du Wissen brauchst.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Keksik senkt seine Pfoten. Ich habe alles getan, was ich konnte. Keine Erinnerungen mehr. Ich hoffe, du kommst zur Besinnung.",
                "image": "kex_final_1.png"
            }
        ]
    },
    'fr': {  # Французский
        "friendly": [
            {
                "text": "Salut ! Keksik ici 🐱 Tes sujets te manquent ! Un petit rappel - et tu seras de retour dans le rythme !",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Hé-hé ! Keksik en ligne 😺 Tes connaissances n'attendent que tu les rafraîchisses ! Seulement 5 minutes - et tu seras génial !",
                "image": "kex_friendly_1.png"
            },
            {
                "text": "Miaou ! Keksik ici 🐾 Tu te souviens comme c'était génial de voir les progrès ? Continuons ! Tes sujets t'attendent !",
                "image": "kex_friendly_1.png"
            }
        ],
        "sad": [
            {
                "text": "Keksik est triste... 😿 Tes sujets n'ont pas vu de répétitions depuis longtemps. Juste quelques minutes - et je ronronnerai à nouveau !",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Oh... Keksik est assis seul 🐱 Tes connaissances sont lentement oubliées. Ne les laissons pas disparaître !",
                "image": "kex_sad_1.png"
            },
            {
                "text": "Keksik soupire... Tu as si bien commencé ! N'abandonne pas maintenant - viens juste marquer quelques répétitions !",
                "image": "kex_sad_1.png"
            }
        ],
        "angry": [
            {
                "text": "Keksik est en colère ! 😾 Tu as promis d'étudier régulièrement ! Arrête de procrastiner - il est temps d'agir !",
                "image": "kex_angry_1.png"
            },
            {
                "text": "Frrr ! Keksik est mécontent ! Tes sujets accumulent la poussière ! Ressaisis-toi et continue le chemin vers la connaissance !",
                "image": "kex_angry_1.png"
            },
            {
                "text": "SSH ! Keksik est furieux ! Tant d'efforts - et tout est parti ? Non ! Reviens et termine ce que tu as commencé !",
                "image": "kex_angry_1.png"
            }
        ],
        "final_warning": [
            {
                "text": "C'est tout. Keksik abandonne. 😾 Je ne te rappellerai plus. Si tu veux - reviens par toi-même. Au revoir.",
                "image": "kex_final_1.png"
            },
            {
                "text": "C'est le dernier rappel. Keksik est fatigué de lutter contre ton indifférence. Décide par toi-même si tu as besoin de connaissances.",
                "image": "kex_final_1.png"
            },
            {
                "text": "Keksik baisse ses pattes. J'ai fait tout ce que je pouvais. Plus de rappels. J'espère que tu reprends tes esprits.",
                "image": "kex_final_1.png"
            }
        ]
    }
}

# Сообщения для других ситуаций (можно расширять)
DAILY_REMINDERS = {
    'ru': {
        "motivational": [
            "Твой мозг жаждет знаний! Покорми его повторениями! 🐱",
            "Всего 5 минут повторений - и твой день станет продуктивнее! ✨",
            "Не откладывай на завтра то, что можно повторить сегодня! 🚀"
        ]
    },
    'en': {
        "motivational": [
            "Your brain craves knowledge! Feed it with repetitions! 🐱",
            "Just 5 minutes of repetitions - and your day will become more productive! ✨",
            "Don't put off until tomorrow what you can review today! 🚀"
        ]
    },
    'es': {
        "motivational": [
            "¡Tu cerebro anhela conocimiento! ¡Aliméntalo con repeticiones! 🐱",
            "¡Solo 5 minutos de repeticiones - y tu día será más productivo! ✨",
            "¡No dejes para mañana lo que puedes repasar hoy! 🚀"
        ]
    },
    'zh': {
        "motivational": [
            "你的大脑渴望知识！用重复喂养它！🐱",
            "只需5分钟的重复 - 你的一天就会变得更有成效！✨",
            "不要把今天可以复习的事情推迟到明天！🚀"
        ]
    },
    'de': {
        "motivational": [
            "Dein Gehirn sehnt sich nach Wissen! Füttere es mit Wiederholungen! 🐱",
            "Nur 5 Minuten Wiederholungen - und dein Tag wird produktiver! ✨",
            "Verschiebe nicht auf morgen, was du heute wiederholen kannst! 🚀"
        ]
    },
    'fr': {
        "motivational": [
            "Ton cerveau a soif de connaissances ! Nourris-le avec des répétitions ! 🐱",
            "Juste 5 minutes de répétitions - et ta journée deviendra plus productive ! ✨",
            "Ne remets pas à demain ce que tu peux réviser aujourd'hui ! 🚀"
        ]
    }
}


# Функция для получения перевода
def get_text(key: str, lang: str = 'ru', **kwargs) -> str:
    """Получить текст на нужном языке"""
    if lang not in TRANSLATIONS:
        lang = 'ru'

    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['ru'].get(key, key))

    # Заменяем плейсхолдеры
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass

    return text


# Функция для получения сообщения Кекса
def get_kex_message(mood: str, lang: str = 'ru'):
    """Получить случайное сообщение Кекса по настроению и языку"""
    if lang not in KEX_MESSAGES:
        lang = 'ru'

    messages = KEX_MESSAGES[lang].get(mood, KEX_MESSAGES['ru'].get(mood, []))
    return random.choice(messages) if messages else None


# Функция для получения ежедневного напоминания
def get_daily_reminder(lang: str = 'ru'):
    """Получить случайное мотивационное сообщение"""
    if lang not in DAILY_REMINDERS:
        lang = 'ru'

    messages = DAILY_REMINDERS[lang].get("motivational", DAILY_REMINDERS['ru'].get("motivational", []))
    return random.choice(messages) if messages else "Let's study! 📚"


# Функция для создания основной клавиатуры
def get_main_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Получить основную клавиатуру на нужном языке"""
    if lang not in TRANSLATIONS:
        lang = 'ru'

    buttons = TRANSLATIONS[lang]['main_keyboard']
    return ReplyKeyboardMarkup(
        [buttons[:2], buttons[2:4], [buttons[4]]],
        resize_keyboard=True
    )