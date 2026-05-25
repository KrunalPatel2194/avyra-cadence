// Set up global polyfills before loading expo-router
if (typeof global !== "undefined" && !global.DOMRectReadOnly) {
  global.DOMRectReadOnly = class DOMRectReadOnly {
    constructor(x = 0, y = 0, width = 0, height = 0) {
      this.x = x;
      this.y = y;
      this.width = width;
      this.height = height;
    }
    get top() { return this.y; }
    get left() { return this.x; }
    get bottom() { return this.y + this.height; }
    get right() { return this.x + this.width; }
    toJSON() { return { x: this.x, y: this.y, width: this.width, height: this.height }; }
  };
}

// Now load the actual app entry
require('expo-router/entry');
