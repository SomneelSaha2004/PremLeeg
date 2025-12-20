import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Heading,
  HStack,
  Spinner,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Text,
  Badge,
} from '@chakra-ui/react';

import { fetchGoldenPrompts, fetchSchema } from './api.js';
import SchemaTab from './components/SchemaTab.jsx';
import ChatTab from './components/ChatTab.jsx';
import GuidelinesTab from './components/GuidelinesTab.jsx';
import ArchitectureTab from './components/ArchitectureTab.jsx';

export default function App() {
  const [schema, setSchema] = useState(null);
  const [golden, setGolden] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const [schemaData, goldenData] = await Promise.all([
          fetchSchema(),
          fetchGoldenPrompts(5),
        ]);
        if (cancelled) return;
        setSchema(schemaData);
        setGolden(goldenData);
      } catch (e) {
        if (cancelled) return;
        setLoadError(e?.message || 'Failed to load initial data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const relationCount = useMemo(() => schema?.relations?.length || 0, [schema]);

  return (
    <Box>
      <HStack justify="space-between" align="start" mb={6}>
        <Box>
          <Heading size="lg">PremLeeg Demo Dashboard</Heading>
          <Text color="gray.600">
            Explore the database schema and try natural-language queries.
          </Text>
        </Box>
        <Badge colorScheme="purple" mt={2}>
          {relationCount} relations
        </Badge>
      </HStack>

      {loading ? (
        <HStack gap={3}>
          <Spinner />
          <Text>Loading schema + examples…</Text>
        </HStack>
      ) : loadError ? (
        <Box borderWidth="1px" borderRadius="md" p={4}>
          <Heading size="sm" mb={1}>
            Could not load demo data
          </Heading>
          <Text color="red.600">{loadError}</Text>
          <Text color="gray.600" mt={2}>
            Make sure the backend is running on port 8000.
          </Text>
        </Box>
      ) : (
        <Tabs isFitted variant="enclosed">
          <TabList mb="1em">
            <Tab>Schema</Tab>
            <Tab>Chat</Tab>
            <Tab>Guidelines</Tab>
            <Tab>Architecture</Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              <SchemaTab schema={schema} />
            </TabPanel>
            <TabPanel>
              <ChatTab goldenPrompts={golden} />
            </TabPanel>
            <TabPanel>
              <GuidelinesTab goldenPrompts={golden} />
            </TabPanel>
            <TabPanel>
              <ArchitectureTab />
            </TabPanel>
          </TabPanels>
        </Tabs>
      )}
    </Box>
  );
}
