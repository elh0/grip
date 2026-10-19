import { Tabs } from 'expo-router/js-tabs';

import { TabBar } from '@/components/tab-bar';
import { color } from '@/constants/theme';

/** Climbs (your reviews), New sets (the free feed), Gyms (follow for alerts), You (projects, sends, plan). */
export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: color.dark.bg } }}>
      <Tabs.Screen name="index" options={{ title: 'Climbs' }} />
      <Tabs.Screen name="sets" options={{ title: 'New sets' }} />
      <Tabs.Screen name="gyms" options={{ title: 'Gyms' }} />
      <Tabs.Screen name="you" options={{ title: 'You' }} />
    </Tabs>
  );
}
