import pprint
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def run_full_stepik_parser():
    # Актуальные названия папок строго по вашему скриншоту
    target_folders = [
        "В тренде",
        "Новые курсы",
        "Курсы с поддержкой",
        "Подготовка к ЕГЭ и ОГЭ",
        "ИИ на каждый день"
    ]

    # Настройки визуального браузера Chrome
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")  # Открываем сразу на весь экран
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)

    # Словарь, который заполнится динамически на Этапе 1
    folder_course_ids = {}

    try:
        # =====================================================================
        # ЭТАП 1: Автоматический сбор числовых ID курсов по вкладкам каталога
        # =====================================================================
        print("Этап 1: Открываем каталог Stepik и собираем ID курсов...")
        driver.get("https://stepik.org")
        time.sleep(5)  # Ожидаем базовую отрисовку SPA-интерфейса

        # Находим все элементы кнопок-вкладок на панели категорий
        buttons = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//button[@role='tab'] | //button[contains(@class, 'tab')] | //button")
        ))

        for folder_name in target_folders:
            for btn in buttons:
                btn_text = btn.text.strip()
                if folder_name.lower() in btn_text.lower():
                    try:
                        # Скроллим к кнопке вкладки по центру экрана, чтобы её не перекрывала шапка
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.5)

                        # Совершаем клик через JS
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"-> Кликнули по вкладке '{folder_name}', ожидаем подгрузку карусели...")
                        time.sleep(4)  # Даем время на обновление карточек в DOM

                        # Собираем все ссылки на курсы
                        course_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/course/')]")

                        ids = []
                        for link in course_links:
                            try:
                                href = link.get_attribute("href")
                                if href and "/course/" in href:
                                    # Извлекаем только числовой идентификатор регулярным выражением
                                    match = re.search(r'/course/(\d+)', href)
                                    if match:
                                        course_id = int(match.group(1))
                                        if course_id not in ids:
                                            ids.append(course_id)
                            except Exception:
                                continue

                        if ids:
                            # Забираем строго 11 уникальных ID курсов по вашему ТЗ
                            folder_course_ids[folder_name] = ids[:11]
                            print(f"   [Успех] Для папки '{folder_name}' динамически собрано {len(ids[:11])} ID.")
                        else:
                            print(f"⚠️ Для папки '{folder_name}' не удалось найти ссылки на курсы.")
                    except Exception as e:
                        print(f"Ошибка при сборе ID для вкладки '{folder_name}': {e}")
                    break

        # Проверяем, заполнился ли наш словарь перед переходом к следующему шагу
        if not folder_course_ids:
            print("\n❌ Критическая ошибка: Не удалось собрать ID ни для одной папки. Завершение работы.")
            return
        # =====================================================================
        # ЭТАП 2: Поочередный обход промо-страниц /promo и извлечение полей
        # =====================================================================
        print("\nЭтап 2: Переходим к сбору параметров по ссылкам типа /course/ID/promo...")

        count_folder = 0
        for folder_name, ids in folder_course_ids.items():
            count_folder += 1
            print(f"\n==================================================")
            print(f"СПИСОК №{count_folder} — ПАПКА: '{folder_name}' (Всего карточек: {len(ids)})")
            print(f"==================================================")

            final_cards_list = []

            for cid in ids:
                promo_url = f"https://stepik.org/course/{cid}/promo"

                # ДОБАВЛЕНО: Механизм повторных попыток (Retries) для защиты от ERR_NAME_NOT_RESOLVED
                connected = False
                for attempt in range(3):
                    try:
                        driver.get(promo_url)
                        time.sleep(2)  # Пауза для стабильной отрисовки блоков
                        connected = True
                        break  # Если успешно зашли, выходим из цикла попыток
                    except Exception as net_error:
                        print(f"   [Попытка {attempt + 1}/3] Сетевая задержка для ID {cid}, ожидаем прогрузки...")
                        time.sleep(3)  # Делаем паузу перед повторным запросом

                if not connected:
                    print(f"   [-] Не удалось открыть промо-страницу для ID {cid} после 3 попыток.")
                    continue

                try:
                    # 1. Название (Из главного h1 страницы)
                    try:
                        title = wait.until(EC.presence_of_element_located(
                            (By.XPATH, "//h1 | //*[contains(@class, 'title')]")
                        )).text.strip()
                    except Exception:
                        title = "NULL"

                    # 2. Автор / Инструктор (берем строго первую строчку)
                    try:
                        author_raw = driver.find_element(
                            By.XPATH,
                            "//*[contains(@class, 'author')] | //*[contains(@class, 'instructor')] | //a[contains(@href, '/users/')]"
                        ).text.strip()

                        # Разрезаем полученный текст по переносу строки и забираем только имя
                        author = author_raw.split('\n')[0].strip() if author_raw else "Stepik"
                        if not author:
                            author = "Stepik"
                    except Exception:
                        author = "Stepik"

                    # 3. Оценка
                    try:
                        rating_text = driver.find_element(By.XPATH,
                                                          "//*[contains(@class, 'rating') or contains(@class, 'score')]").text.strip()
                        rating_match = re.search(r'\d+\.\d+|\d+', rating_text)
                        rating = round(float(rating_match.group(0)), 2) if rating_match else "NULL"
                    except Exception:
                        rating = "NULL"

                    # 4. Количество студентов
                    try:
                        students_text = driver.find_element(By.XPATH, "//*[contains(text(), 'учащих')]").text.strip()
                        students_match = re.search(r'\d+', students_text.replace(" ", "").replace("\xa0", ""))
                        students = int(students_match.group(0)) if students_match else "NULL"
                    except Exception:
                        students = "NULL"

                    # 5. Время прохождения
                    time_to_complete = "Не указано"
                    try:
                        meta_items = driver.find_elements(By.XPATH,
                                                          "//*[contains(@class, 'meta__item')] | //*[contains(@class, 'duration')]")
                        for item in meta_items:
                            item_text = item.text.strip()
                            if any(word in item_text.lower() for word in ["час", "модул", "недел", "лекц"]):
                                time_to_complete = item_text
                                break
                    except Exception:
                        pass

                    # 6. Наличие сертификата
                    try:
                        page_html = driver.page_source.lower()
                        has_cert = "Да" if "сертификат" in page_html or "certificate" in page_html else "NULL"
                    except Exception:
                        has_cert = "NULL"

                    # 7. Стоимость (Вывод двух цен через '/' при наличии скидки/акции)
                    try:
                        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                        if "бесплатно" in page_text or "поступить на курс" in page_text:
                            cost = "бесплатно"
                        else:
                            price_elements = driver.find_elements(By.XPATH,
                                                                  "//*[contains(text(), '₽') or contains(@class, 'price')]")
                            prices = []
                            for p in price_elements:
                                p_clean = re.sub(r'[^\d]', '', p.text.strip())
                                if p_clean and p_clean not in prices:
                                    prices.append(f"{p_clean} ₽")

                            # Форматируем вывод цен через косую черту по вашему ТЗ
                            if len(prices) >= 2:
                                cost = f"{prices[0]} / {prices[1]}"
                            elif len(prices) == 1:
                                cost = prices[0]
                            else:
                                cost = "бесплатно"
                    except Exception:
                        cost = "бесплатно"

                    card_data = {
                        "Название": title,
                        "Автор": author,
                        "Оценка": rating,
                        "Количество студентов": students,
                        "Время прохождения": time_to_complete,
                        "Наличие сертификата": has_cert,
                        "Стоимость": cost
                    }
                    final_cards_list.append(card_data)
                    print(f"   [+] Обработан курс ID {cid} -> {title[:35]}...")

                except Exception as card_error:
                    print(f"   [-] Ошибка при парсинге карточки ID {cid}: {card_error}")
                    continue

            # Выплевываем полностью готовый список из 11 карточек папки в логи терминала PyCharm
            pprint.pprint(final_cards_list, sort_dicts=False)

    finally:
        # Браузер закрывается строго в самом конце, после выполнения всех этапов
        driver.quit()
        print("\nПолный цикл автоматического парсинга успешно завершен!")


if __name__ == "__main__":
    run_full_stepik_parser()

