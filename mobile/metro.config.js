const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Reduce file watching overhead for large node_modules
config.watchFolders = [__dirname];
config.projectRoot = __dirname;

module.exports = config;
