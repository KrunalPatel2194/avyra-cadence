// Polyfill for DOMRectReadOnly
class DOMRectReadOnly {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;

  constructor(x: number = 0, y: number = 0, width: number = 0, height: number = 0) {
    this.x = x;
    this.y = y;
    this.width = width;
    this.height = height;
  }

  get top(): number {
    return this.y;
  }

  get left(): number {
    return this.x;
  }

  get bottom(): number {
    return this.y + this.height;
  }

  get right(): number {
    return this.x + this.width;
  }

  toJSON() {
    return {
      top: this.top,
      left: this.left,
      bottom: this.bottom,
      right: this.right,
      x: this.x,
      y: this.y,
      width: this.width,
      height: this.height,
    };
  }
}

// Register globally
(global as any).DOMRectReadOnly = DOMRectReadOnly;

export { DOMRectReadOnly };
