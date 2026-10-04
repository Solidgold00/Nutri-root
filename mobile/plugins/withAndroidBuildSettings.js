const { withGradleProperties } = require('@expo/config-plugins');

const ANDROID_BUILD_SETTINGS = {
  reactNativeArchitectures: 'arm64-v8a',
  newArchEnabled: 'false',
  hermesEnabled: 'false',
};

module.exports = function withAndroidBuildSettings(config) {
  return withGradleProperties(config, (updatedConfig) => {
    for (const [key, value] of Object.entries(ANDROID_BUILD_SETTINGS)) {
      const existing = updatedConfig.modResults.find(
        (item) => item.type === 'property' && item.key === key,
      );

      if (existing) {
        existing.value = value;
      } else {
        updatedConfig.modResults.push({ type: 'property', key, value });
      }
    }

    return updatedConfig;
  });
};
