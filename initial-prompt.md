 nos temos uma ferramenta que utilizamos para baixar dados de nossos datapackages (padrao frictionless data) que estão em nossos repositorios git. Essa
    ferramenta é o DPM e está no repo https://github.com/splor-mg/dpm e tem um mkdocs aqui: https://splor-mg.github.io/dpm/                                     
  Aprenda como o dpm funciona e crie aqui nesta pasta um mcp dele. O dpm original continuara sendo um pacote python lá em seu repo, aqui será construída outra
  ferramenta que é o dpm-mcp

  Utilize o que há de mais moderno e robusto para construí-lo, e faça que qualquer agente possa se conectar a ele e utilizar suas funcoes (sendo a mais
  importante de todas baixar os dados para uso).

  Também adicione uma função que receba um nome de org ou de usuário e consiga listar todos os datapackages la presentes. Por exemplo, eu passso como
  parametro a org splor-mg e ele lista todos os datapackages la presentes e dai eu poderia baixar todos que lá estão. O mesmo para um usuário. Também deve
  haver a opção de somente passar a url do repo e ele baixar os dados caso seja um datapackage. Se atente também a todoas as parametrizações do dpm, que
  possibilitam baixar resources especificas ao invess de todas, definir onde os dados serão salvos, etc. eu decidirei depois se ele aceitára github PAT para
  poder acessar repositórios privados ou se trabalhará com base na sua permissão git que vocÊ esta logado no seu ambiente dev. De toda forma implemente o
  projeto já o preparando para trabalhar com PAT e repos privados. O dpm-mcp nunca irá escrever, pushar ou upload de nada para os repositórios que ele
  interagir.

  crie o planejamento e logo em seguida comece a implementação.
