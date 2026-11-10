import type { Exhibit } from './runtime';

export async function prepareStoryExhibit(id: string): Promise<() => Exhibit> {
  switch (id) {
    case 'terra-e-atmosfera':
    case 'sistema-solar': {
      const { prepareStoryWorlds, createWorldStory } = await import('./story-worlds');
      await prepareStoryWorlds(id);
      return () => createWorldStory(id);
    }
    case 'galaxias-e-nebulosas':
    case 'misterios-do-cosmos': {
      const { prepareStoryGalaxies, createGalaxyStory } = await import('./story-galaxies');
      await prepareStoryGalaxies(id);
      return () => createGalaxyStory(id);
    }
    case 'vida-das-estrelas': {
      const { prepareStoryStars, createStarStory } = await import('./story-stars');
      await prepareStoryStars();
      return createStarStory;
    }
    case 'origem-do-universo': {
      const { createRedshiftStory } = await import('./story-redshift');
      return createRedshiftStory;
    }
    default: throw new RangeError(`Aula sem cena 3D: ${id}`);
  }
}
