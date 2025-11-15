---
layout: page
---
<script setup>
import {
  VPTeamPage,
  VPTeamPageTitle,
  VPTeamMembers,
  VPTeamPageSection
} from 'vitepress/theme'

const coreTeam = [
  {
    avatar: 'https://avatars.githubusercontent.com/u/144450118?v=4',
    name: "Dunamix",
    title: 'Creator | Lead Developer',
    desc: 'Core architect and maintainer of Nexios. Focused on async performance and clean architecture.',
    links: [
      { icon: 'github', link: 'https://github.com/TechWithDunamix' },
      { icon: 'twitter', link: 'https://twitter.com/mrdunamix' }
    ],
    sponsor: 'https://github.com/sponsors/TechWithDunamix'
  }
]

const maintainers = [
  {
    avatar: 'https://avatars.githubusercontent.com/u/55154055?v=4',
    name: "Mohammed Al-Ameen",
    title: 'Core Developer',
    desc: 'Creator of the nexios file router system',
    links: [
      { icon: 'github', link: 'https://github.com/struckchure' },
      { icon: 'twitter', link: 'https://x.com/struckchure' }
    ]
  },
  {
    avatar: 'https://avatars.githubusercontent.com/u/30089712?v=4',
    name:'Dao Malick BENIN',
    title:'Contributor',
    desc:'',
    links: [
      { icon: 'github', link: 'https://github.com/dmb225' },
      { icon: 'linkedin', link: 'https://www.linkedin.com/in/dao-malick-benin' }
    ]
  },
  {
    avatar: 'https://avatars.githubusercontent.com/u/102381259?v=4',
    name:'ivan',
    title:'Contributor',
    desc:'',
    links: [
      { icon: 'github', link: 'https://github.com/iamlostshe' },
      { icon: 'youtube', link: 'https://www.youtube.com/@iamlostshe' }
    ]
  }
]

const emeriti = [
  // Past team members who made significant contributions
]
</script>

<VPTeamPage>
  <VPTeamPageTitle>
    <template #title>
      Our Team
    </template>
    <template #lead>
      The development of Nexios is guided by an experienced team of developers who are passionate about building fast, clean, and developer-friendly web frameworks. The project thrives thanks to contributions from our amazing community.
    </template>
  </VPTeamPageTitle>

  <VPTeamPageSection>
    <template #title>Core Team</template>
    <template #lead>The core development team behind Nexios.</template>
    <template #members>
      <VPTeamMembers size="medium" :members="coreTeam" />
    </template>
  </VPTeamPageSection>

  <VPTeamPageSection>
    <template #title>Maintainers</template>
    <template #lead>Active maintainers helping to ensure Nexios's continued development and success.</template>
    <template #members>
      <VPTeamMembers size="medium" :members="maintainers" />
    </template>
  </VPTeamPageSection>

  
</VPTeamPage>

