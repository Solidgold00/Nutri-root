import { StyleSheet, Text, View } from 'react-native';

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metric: {
    flex: 1,
    minWidth: 100,
    padding: 14,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E8ECE5',
  },
  value: {
    fontSize: 19,
    fontWeight: '800',
    color: '#172118',
  },
  label: {
    marginTop: 4,
    fontSize: 12,
    color: '#667064',
  },
});
