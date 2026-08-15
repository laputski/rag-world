// Preparing the environment for the interface tests.
import "@testing-library/jest-dom/vitest";

// The resize observer is not implemented in the test environment while the
// charts use it to fit their container. A stub is enough: the layout is not what
// the tests check, the behaviour is.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (!("ResizeObserver" in globalThis)) {
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver = ResizeObserverStub;
}
