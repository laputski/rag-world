// Подготовка среды для тестов интерфейса.
import "@testing-library/jest-dom/vitest";

// Наблюдатель за размерами элемента в тестовой среде не реализован, а диаграммы
// используют его для подстройки под контейнер. Заглушка достаточна: геометрия
// в тестах не проверяется, проверяется поведение.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (!("ResizeObserver" in globalThis)) {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
}
