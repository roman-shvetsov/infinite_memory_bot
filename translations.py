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

        'active_topics_count': "📊 Активных тем: {current}/{max}",
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

        'active_topics_count': "📊 Active topics: {current}/{max}",
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
    }
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