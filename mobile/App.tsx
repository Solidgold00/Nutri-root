import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Metric } from './src/components/Metric';
import { analyzeMeal } from './src/lib/api';
import { AnalysisResult } from './src/lib/types';

const examples = [
  'I had 2 scoops of egusi, one wrap of pounded yam and two small pieces of beef',
  'A bowl of waakye, one piece of grilled tilapia and 2 tablespoons of shito',
  'One plate of ceebu jën with a glass of coconut water',
  'One wrap of eba, two ladles of okra soup and one piece of goat meat',
];

function compactCountries(countries: string[]) {
  if (countries.length <= 4) return countries.join(' · ');
  return `${countries.slice(0, 4).join(' · ')} · +${countries.length - 4}`;
}

export default function App() {
  const [meal, setMeal] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit() {
    const cleaned = meal.trim();
    if (!cleaned) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      setResult(await analyzeMeal(cleaned));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not analyse meal.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor="#F5F7F2" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View>
            <Text style={styles.brand}>NUTRIROOT</Text>
            <Text style={styles.catalogueLine}>V0.4 · 101 foods · 16 West African countries</Text>
          </View>
          <Text style={styles.hero}>Understand what you’re actually eating.</Text>
          <Text style={styles.subhero}>
            UK-focused Nigerian and West African nutrition analysis with published source profiles,
            transparent baseline recipes and estimated PRAL.
          </Text>

          <View style={styles.inputCard}>
            <Text style={styles.label}>What did you eat?</Text>
            <TextInput
              value={meal}
              onChangeText={setMeal}
              placeholder="e.g. Egusi soup, pounded yam and 2 pieces of beef"
              placeholderTextColor="#8B9388"
              multiline
              style={styles.input}
            />
            <Pressable
              onPress={submit}
              disabled={loading || !meal.trim()}
              style={({ pressed }) => [
                styles.button,
                (pressed || loading || !meal.trim()) && styles.buttonMuted,
              ]}
            >
              {loading ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.buttonText}>Analyse meal</Text>}
            </Pressable>
          </View>

          {!result && !loading && (
            <View style={styles.examples}>
              <Text style={styles.sectionTitle}>Try an example</Text>
              {examples.map((example) => (
                <Pressable key={example} onPress={() => setMeal(example)} style={styles.exampleChip}>
                  <Text style={styles.exampleText}>{example}</Text>
                </Pressable>
              ))}
            </View>
          )}

          {!!error && <Text style={styles.error}>{error}</Text>}

          {result && (
            <View style={styles.results}>
              <View style={styles.resultHeader}>
                <View style={styles.flex}>
                  <Text style={styles.eyebrow}>ESTIMATED ANALYSIS</Text>
                  <Text style={styles.resultTitle}>{result.query}</Text>
                  <Text style={styles.parserNote}>{result.parser === 'ai' ? 'AI PARSED' : 'LOCAL PARSER'} · CATALOGUE {result.catalogue_version} · {result.parser_note}</Text>
                  <Text style={styles.qualitySummary}>{result.data_quality_summary}</Text>
                </View>
                <View style={styles.confidencePill}>
                  <Text style={styles.confidenceText}>{result.confidence.toUpperCase()}</Text>
                </View>
              </View>

              <View style={styles.metricGrid}>
                <Metric label="Calories" value={`${Math.round(result.nutrients.calories_kcal)} kcal`} />
                <Metric label="Protein" value={`${result.nutrients.protein_g.toFixed(1)} g`} />
                <Metric label="Carbs" value={`${result.nutrients.carbs_g.toFixed(1)} g`} />
                <Metric label="Fat" value={`${result.nutrients.fat_g.toFixed(1)} g`} />
                <Metric label="Fibre" value={`${result.nutrients.fibre_g.toFixed(1)} g`} />
                <Metric label="Sodium" value={`${Math.round(result.nutrients.sodium_mg)} mg`} />
              </View>

              <View style={styles.pralCard}>
                <Text style={styles.eyebrow}>ESTIMATED DIETARY ACID LOAD</Text>
                <Text style={styles.pralValue}>{result.pral_meq > 0 ? '+' : ''}{result.pral_meq.toFixed(1)} mEq</Text>
                <Text style={styles.pralLabel}>{result.pral_label}</Text>
                <Text style={styles.body}>{result.explanation}</Text>
              </View>

              <View style={styles.mineralCard}>
                <Text style={styles.sectionTitle}>Key minerals</Text>
                <Text style={styles.mineralLine}>Potassium  {Math.round(result.nutrients.potassium_mg)} mg</Text>
                <Text style={styles.mineralLine}>Calcium  {Math.round(result.nutrients.calcium_mg)} mg</Text>
                <Text style={styles.mineralLine}>Magnesium  {Math.round(result.nutrients.magnesium_mg)} mg</Text>
                <Text style={styles.mineralLine}>Phosphorus  {Math.round(result.nutrients.phosphorus_mg)} mg</Text>
              </View>

              <View style={styles.sourcesCard}>
                <Text style={styles.sectionTitle}>What was recognised?</Text>
                {result.components.map((item, index) => (
                  <View style={styles.componentCard} key={`${item.matched_food}-${index}`}>
                    <Text style={styles.component}>• {item.quantity} {item.unit}{item.quantity === 1 ? '' : 's'} → {item.matched_food}</Text>
                    <Text style={styles.componentMeta}>≈ {item.grams.toFixed(0)} g · {item.data_quality.replaceAll('_', ' ')} · portion {item.portion_confidence}</Text>
                    <Text style={styles.countryLine}>{compactCountries(item.countries)}</Text>
                    <Text style={styles.sourceLine}>{item.source}</Text>
                    <Text style={styles.profileLine}>Profiles: {item.source_profile_codes.join(', ')}</Text>
                    <Text style={styles.sourceNote}>{item.source_note}</Text>
                  </View>
                ))}
                <Text style={styles.disclaimer}>{result.disclaimer}</Text>
              </View>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F5F7F2' },
  flex: { flex: 1 },
  container: { padding: 22, paddingBottom: 48, gap: 18 },
  brand: { fontSize: 13, fontWeight: '900', letterSpacing: 2.5, color: '#3A6642', marginTop: 10 },
  catalogueLine: { marginTop: 5, fontSize: 11, fontWeight: '700', color: '#778174' },
  hero: { fontSize: 38, lineHeight: 42, fontWeight: '900', color: '#172118', maxWidth: 500 },
  subhero: { fontSize: 16, lineHeight: 23, color: '#5D675B', maxWidth: 540 },
  inputCard: { backgroundColor: '#FFFFFF', borderRadius: 22, padding: 18, borderWidth: 1, borderColor: '#E5EAE2', gap: 12 },
  label: { fontSize: 14, fontWeight: '800', color: '#293528' },
  input: { minHeight: 110, borderRadius: 16, backgroundColor: '#F6F8F4', padding: 14, color: '#172118', fontSize: 16, textAlignVertical: 'top' },
  button: { minHeight: 54, alignItems: 'center', justifyContent: 'center', borderRadius: 16, backgroundColor: '#234B2A' },
  buttonMuted: { opacity: 0.55 },
  buttonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  examples: { gap: 9 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#283426', marginBottom: 4 },
  exampleChip: { paddingVertical: 12, paddingHorizontal: 14, borderRadius: 14, backgroundColor: '#EAF0E6' },
  exampleText: { color: '#38513B', fontWeight: '600' },
  error: { color: '#A52A2A', backgroundColor: '#FFF0F0', padding: 14, borderRadius: 14 },
  results: { gap: 14 },
  resultHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  eyebrow: { fontSize: 11, letterSpacing: 1.4, fontWeight: '900', color: '#6E796B' },
  resultTitle: { marginTop: 5, fontSize: 23, lineHeight: 28, fontWeight: '900', color: '#172118', textTransform: 'capitalize' },
  parserNote: { marginTop: 7, color: '#687466', fontSize: 11, lineHeight: 16, fontWeight: '700' },
  qualitySummary: { marginTop: 7, color: '#405141', fontSize: 12, lineHeight: 17, fontWeight: '700' },
  confidencePill: { backgroundColor: '#DDE9D9', borderRadius: 99, paddingHorizontal: 11, paddingVertical: 7 },
  confidenceText: { fontSize: 10, fontWeight: '900', color: '#36563A', letterSpacing: 0.8 },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },
  pralCard: { padding: 18, borderRadius: 22, backgroundColor: '#1E3522', gap: 6 },
  pralValue: { marginTop: 5, fontSize: 36, fontWeight: '900', color: '#FFFFFF' },
  pralLabel: { fontSize: 15, fontWeight: '800', color: '#DDE8DA' },
  body: { marginTop: 8, color: '#E6EDE4', lineHeight: 21 },
  mineralCard: { padding: 18, borderRadius: 22, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5EAE2' },
  mineralLine: { color: '#556054', paddingVertical: 4, fontSize: 14 },
  sourcesCard: { padding: 18, borderRadius: 22, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5EAE2' },
  componentCard: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#EEF1EC' },
  component: { color: '#364236', paddingVertical: 2, fontWeight: '700' },
  componentMeta: { color: '#5D695D', fontSize: 12, paddingTop: 2 },
  countryLine: { color: '#566C56', fontSize: 11, lineHeight: 15, paddingTop: 4, fontWeight: '700' },
  sourceLine: { color: '#315B39', fontSize: 11, fontWeight: '800', paddingTop: 5 },
  profileLine: { color: '#647164', fontSize: 10, lineHeight: 14, paddingTop: 2 },
  sourceNote: { color: '#7A8378', fontSize: 10, lineHeight: 14, paddingTop: 2 },
  disclaimer: { marginTop: 14, color: '#7B8379', fontSize: 11, lineHeight: 16 },
});
