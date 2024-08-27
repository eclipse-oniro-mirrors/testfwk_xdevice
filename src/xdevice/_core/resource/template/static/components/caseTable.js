const caseTable = {
  name: "case-table",
  component: {
    template: `<el-table :data="pageCaseList" style="width: 100%" @sort-change="handleSortChange" class="details-table" border>
    <el-table-column type="index" label="#" min-width="3%"></el-table-column>
    <el-table-column prop="suiteName" label="Testsuite" show-overflow-tooltip="" min-width="28%" width="380" resizable></el-table-column>
    <el-table-column prop="name" label="Testcase" show-overflow-tooltip="" min-width="20%"></el-table-column>
    <el-table-column sortable prop="time" label="Time(s)" min-width="10%">
    </el-table-column>
    <el-table-column label="Result" min-width="10%">
      <template #header>
        <popover-checkbox
          headername="Result"
          :options="resultFilterOption"
          @change="resultFilterChange"
        >
        </popover-checkbox>
      </template>
      <template #default="scope">
        <el-tag
          class="ml-2"
          :type="scope.row.result === 'Passed' ? 'success' : 'danger'"
          >{{ scope.row.result }}</el-tag
        >
      </template>
    </el-table-column>
    <el-table-column prop="error" label="Error" min-width="30%">
      <template #default="scope">
        <el-popover
          placement="bottom"
          width="680"
          trigger="hover"
        >
          <div class="div-popover">
            <el-row class="row-error" v-html="scope.row.error"></el-row>
          </div>
          <template #reference>
            <div class="div-error">
              <span class="span-error">{{scope.row.error.replace(/<br>/g, " ")}}</span>
            </div>
          </template>
        </el-popover>
      </template>
    </el-table-column>
  </el-table>
  <div class="pager">
  <el-pagination
    background
    v-bind="paginationInfo"
    @current-change="handlePageChange"
    @size-change="handleSizeChange"
  />
</div>
  `,
    data() {
      return {
        paginationInfo: {
          layout: "total, sizes, prev, pager, next, jumper",
          total: 0,
          pageSize: 10,
          currentPage: 1,
          pageSizes: [10, 20, 50],
        },
        pageCaseList: [],
        resultFilterOption: [],
        resultFilter: [],
      };
    },
    props: ["list", "keyword", "keyname"],
    mounted() {
      this.initSuiteOiptions();
      this.getPageData();
    },
    methods: {
      handleSortChange({ column, prop, order }) {
        if (column && prop && order) {
          this.list.sort((a, b) => {
            const valueA = a[prop];
            const valueB = b[prop];
            if (order === 'ascending') {
              return valueA > valueB ? 1 : -1;
            } else if (order === 'descending') {
              return valueA < valueB ? 1 : -1;
            }
            return 0;
          });
        }
        this.paginationInfo.currentPage = 1;
        this.getPageData();
      },
      getPageData() {
        this.pageCaseList.length = 0;
        const { pageSize, currentPage } = this.paginationInfo;
        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        let filterData = [...this.list];
        if (this.keyname) {
          filterData = filterData.filter((item) => {
            return item[0] == this.keyname;
          });
        }
        if (this.resultFilter.length > 0) {
          filterData = filterData.filter((item) =>
            this.resultFilter.includes(item[2])
          );
        }
        if (this.keyword) {
          filterData = filterData.filter(item => item[1].toLowerCase().includes(this.keyword.toLowerCase()))
        }
        this.paginationInfo.total = filterData.length;
        const pageData = filterData.slice(startIndex, endIndex);
        let results = [];
        pageData.forEach((item) => {
          let [suiteName, name, result, time, error] = item;
          results.push({ suiteName, name, result, time, error });
        })
        this.pageCaseList = results;
        this.pageCaseList.forEach(item => {
          if (item.error) {
            item.error = item.error.replace(/\r\n/g, "<br>").replace(/\n/g, "<br>")
          }
        });
      },
      initSuiteOiptions() {
        this.resultFilterOption = [...new Set(this.list.map((item) => item[2]))];
      },
      resultFilterChange(val) {
        this.resultFilter.length = 0;
        this.paginationInfo.currentPage = 1;
        this.resultFilter.push(...val);
        this.getPageData();
      },
      handlePageChange(pageNum) {
        this.paginationInfo.currentPage = pageNum;
        this.getPageData();
      },
      handleSizeChange(size) {
        this.paginationInfo.currentPage = 1;
        this.paginationInfo.pageSize = size;
        this.getPageData();
      },
      handleSerarch() {
        this.paginationInfo.currentPage = 1;
        this.getPageData();
      },

    },
  },
};
