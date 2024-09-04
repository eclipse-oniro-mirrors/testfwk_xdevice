//
// Copyright (c) 2022 Huawei Device Co., Ltd.
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

const suiteTable = {
  name: "suite-table",
  component: {
    template: `<el-table :data="pageSuitesList" style="width: 100%" border @sort-change="handleSortChange" class="details-table" @row-click="handleRowClick"  row-class-name="table-row-clickable">
    <el-table-column type="index" label="#" min-width="3%"></el-table-column>
    <el-table-column prop="name" label="Testsuite" show-overflow-tooltip="" min-width="27%" resizable
    ></el-table-column>
    <el-table-column sortable prop="time" label="Time(s)" min-width="10%"> </el-table-column>
    <el-table-column sortable prop="tests" label="Tests" min-width="10%"> </el-table-column>
    <el-table-column sortable prop="passed" label="Passed" min-width="10%"> </el-table-column>
    <el-table-column sortable prop="failed" label="Failed" min-width="10%"> 
    <template #default="scope">
              <span :style="[scope.row.failed > 0 ? {'color':'red'}:{}]">{{ scope.row.failed }}</span>
            </template></el-table-column>
    <el-table-column sortable prop="blocked" label="Blocked" min-width="10%">
    <template #default="scope">
              <span :style="[scope.row.blocked > 0 ? {'color':'#ffb400'}:{}]">{{ scope.row.blocked }}</span>
            </template> </el-table-column>
    <el-table-column sortable prop="ignored" label="Ignored" min-width="10%"> </el-table-column>
    <el-table-column sortable prop="passingrate" label="Passing Rate" min-width="10%"> 
      <template #default="scope">
        <el-progress :text-inside="true"
        :stroke-width="22"
        status="success" 
        precision="2"
        :percentage="scope.row.passingrate" 
        :color="customColorMethod(scope.row.passingrate)" />
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
  </div>`,
    data() {
      return {
        paginationInfo: {
          layout: "total, sizes, prev, pager, next, jumper",
          total: 0,
          pageSize: 10,
          currentPage: 1,
          pageSizes: [10, 20, 50],
        },
        pageSuitesList: [],
      };
    },
    emits: ["view-detail"],
    props: ["list", "keyword"],
    mounted() {
      this.getPageData();
    },
    methods: {
      customColorMethod(percentage) {
        if (percentage < 50) {
          return 'red'
        }
        if (percentage < 100) {
          return '#ffb400'
        }
        return '#67c23a'
      },
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
        this.pageSuitesList.length = 0;
        const { pageSize, currentPage } = this.paginationInfo;
        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        let filterData = [... this.list];
        if (this.keyword) {
          filterData = filterData.filter(item => item.name.toLowerCase().includes(this.keyword.toLowerCase()))
        }
        this.paginationInfo.total = filterData.length;
        const pageData = filterData.slice(startIndex, endIndex);
        this.pageSuitesList.push(...pageData);
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
      handleRowClick(row) {
        this.$emit("view-detail",row);
        setTimeout(() => {
          window.emitter.emit("filter-name", {
            type: "suite",
            value: row.name,
          });
        }, 50);
      },
      handleSerarch() {
        this.paginationInfo.currentPage = 1;
        this.getPageData();
      }
    },
  },
};
