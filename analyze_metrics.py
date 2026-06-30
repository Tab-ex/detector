# analyze_metrics.py
"""
Анализ метрик для расчета ресурсов сервера.
Запуск: python analyze_metrics.py metrics_log.jsonl
"""
import json
import sys
import statistics
from collections import defaultdict

def analyze_log(filepath: str):
    metrics_list = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                metrics_list.append(json.loads(line))
    
    if not metrics_list:
        print(" Нет данных для анализа")
        return
    
    # === АГРЕГАЦИЯ ===
    total_iterations = len(metrics_list)
    timings = defaultdict(list)
    ram_values = []
    cpu_values = []
    
    for m in metrics_list:
        for stage, duration in m["timings"].items():
            timings[stage].append(duration)
        ram_values.append(m["resources"]["rss_mb"])
        cpu_values.append(m["resources"]["cpu_percent"])
    
    # === СТАТИСТИКА ===
    print(f"\n Анализ: {total_iterations} итераций")
    print(f" User ID: {metrics_list[0]['user_id']}")
    print(f"  System: {metrics_list[0]['system']['cpu_logical_cores']} cores, {metrics_list[0]['system']['mem_total_gb']} GB RAM total")
    
    print(f"\n  ТАЙМИНГИ (секунды):")
    for stage in ["record", "feature_extraction", "predict_single", "send_network"]:
        if stage in timings:
            vals = timings[stage]
            print(f"  {stage:20s} | avg: {statistics.mean(vals):.3f} | median: {statistics.median(vals):.3f} | p95: {sorted(vals)[int(len(vals)*0.95)]:.3f}")
    
    total_times = [m["timing_total_sec"] for m in metrics_list]
    print(f"\n ОБЩЕЕ ВРЕМЯ ИТЕРАЦИИ:")
    print(f"  avg: {statistics.mean(total_times):.3f}s | median: {statistics.median(total_times):.3f}s | p95: {sorted(total_times)[int(len(total_times)*0.95)]:.3f}s")
    
    print(f"\n ПАМЯТЬ (RSS, МБ):")
    print(f"  avg: {statistics.mean(ram_values):.1f} | median: {statistics.median(ram_values):.1f} | max: {max(ram_values):.1f} | p95: {sorted(ram_values)[int(len(ram_values)*0.95)]:.1f}")
    
    print(f"\n CPU (% одного ядра):")
    print(f"  avg: {statistics.mean(cpu_values):.1f}% | median: {statistics.median(cpu_values):.1f}% | max: {max(cpu_values):.1f}%")
    
    # === РАСЧЕТ ДЛЯ МАСШТАБИРОВАНИЯ ===
    print(f"\n РАСЧЕТ ПОД 1000 ПОЛЬЗОВАТЕЛЕЙ:")
    
    # Берем p95 для надежности
    time_p95 = sorted(total_times)[int(len(total_times)*0.95)]
    ram_p95 = sorted(ram_values)[int(len(ram_values)*0.95)]
    
    # Если задача полностью последовательная (1 процесс = 1 пользователь)
    total_time_sec = time_p95 * 1000
    total_ram_gb = (ram_p95 * 1000) / 1024
    
    print(f"   Время обработки 1000 запросов (последовательно): {total_time_sec/60:.1f} минут")
    print(f"   Память для 1000 одновременных процессов: {total_ram_gb:.1f} ГБ")
    
    # Если хотим обрабатывать за ~10 секунд (параллельно)
    target_time = 10.0
    needed_cores = (time_p95 * 1000) / target_time
    print(f"   Для обработки за {target_time} сек нужно ~{needed_cores:.0f} ядер (при 100% загрузке)")
    
    # Коэффициент запаса
    safety_factor = 1.3
    print(f"\n С запасом 30%:")
    print(f"  RAM: {total_ram_gb * safety_factor:.1f} ГБ")
    print(f"  CPU cores: {needed_cores * safety_factor:.0f} физических ядер")
    
    print(f"\n Рекомендация:")
    if ram_p95 < 300 and time_p95 < 2.0:
        print("   Задача легкая, можно упаковывать по 4-8 пользователей на ядро (threading/async)")
    elif time_p95 > 5.0:
        print("   Задача тяжелая, выделять 1 ядро на 1-2 пользователя, смотреть в сторону GPU если модель позволяет")
    else:
        print("   Средний профиль, начинать с 1 ядро на пользователя, оптимизировать по мере нагрузки")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python analyze_metrics.py <metrics_log.jsonl>")
        sys.exit(1)
    analyze_log(sys.argv[1])
